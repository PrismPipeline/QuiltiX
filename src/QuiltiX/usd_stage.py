import os
import pathlib
import logging

from qtpy import QtCore # type: ignore

from pxr import Usd, UsdLux, Sdf, Tf, UsdGeom,  UsdShade, Gf  # noqa: E402 # type: ignore
from pxr.Usdviewq._usdviewq import Utils # type: ignore

import MaterialX as mx

from QuiltiX import mx_node
# TODO: decouple from QxNode
from QuiltiX.qx_node import QxNode


logger = logging.getLogger(__name__)


def set_pxr_mtlx_stdlib_search_paths():
    """Usd searches in PXR_MTLX_STDLIB_SEARCH_PATHS for the MaterialX standard library of nodes.
    If it is not set, find the stdlib and set PXR_MTLX_STDLIB_SEARCH_PATHS.
    """
    if not os.getenv("PXR_MTLX_STDLIB_SEARCH_PATHS"):
        os.environ["PXR_MTLX_STDLIB_SEARCH_PATHS"] = ";".join(mx_node.get_mx_stdlib_paths())

    logger.info("stdlib loaded from: %s" % os.environ["PXR_MTLX_STDLIB_SEARCH_PATHS"])


def get_stage_from_file(path):
    if os.path.splitext(path)[1] == ".abc":
        stage = create_empty_stage()
        add_layer_to_stage_root(stage, path)
    else:
        stage = Usd.Stage.Open(path, Usd.Stage.LoadAll)

    return stage


def create_empty_stage():
    return Usd.Stage.CreateInMemory()


def create_stage_with_hdri(hdri_file_path, hdri_parent_path="/lights"):
    stage = create_empty_stage()
    hdri_name = pathlib.Path(hdri_file_path).stem
    hdri_stage_path = "/".join((hdri_parent_path, hdri_name))
    hdri = UsdLux.DomeLight.Define(stage, Sdf.Path(hdri_stage_path))
    hdri.CreateTextureFileAttr(hdri_file_path)
    hdri.CreateTextureFormatAttr("latlong")
    prim = stage.GetPrimAtPath(Sdf.Path(hdri_stage_path))
    attr = prim.CreateAttribute("karma:light:renderlightgeo", Sdf.ValueTypeNames.Bool)
    attr.Set(True)
    # stage.SetDefaultPrim(hdri.GetPrim())
    return stage


def add_layer_to_stage_root(stage, layer_path):
    root = stage.GetRootLayer()
    root.subLayerPaths.insert(0, layer_path)


class MxStageController(QtCore.QObject):

    signal_stage_changed = QtCore.Signal(object)
    signal_stage_updated = QtCore.Signal()

    def __init__(
        self,
        editor=None,
        stage=None,
    ):
        super(MxStageController, self).__init__()
        self.added_layers = []
        self.editor = editor
        self.applied_material = None

    def set_stage(self, stage):
        self.stage = stage
        self.stage_root = self.stage.GetRootLayer()
        self.stage.SetEditTarget(Usd.EditTarget(self.stage.GetSessionLayer()))

        in_memory = os.getenv("QUILTIX_WRITE_TMP_TO_DISK", "0") == "0"
        if in_memory:
            idf = "_tmp_quiltix_assignments.usd"
            self._assignments_layer = Sdf.Layer.CreateAnonymous(idf)
            self._assignments_idf = self._assignments_layer.identifier
        else:
            self._assignments_idf = os.path.join(os.environ["TEMP"], "_tmp_quiltix_assignments.usd")
            self._assignments_layer = Sdf.Layer.CreateNew(self._assignments_idf)

        self.stage_root.subLayerPaths.insert(0, self._assignments_idf)
        self.signal_stage_changed.emit(self.stage)

    def get_all_geo_prims(self):
        return Utils._GetAllPrimsOfType(self.stage, Tf.Type.Find(UsdGeom.Gprim))

    def apply_first_material_to_all_prims(self):
        mx_data = self.editor.qx_node_graph.get_mx_xml_data_from_graph()
        if not mx_data:
            return

        tmp_mx_doc = mx.createDocument()
        mx.readFromXmlString(tmp_mx_doc, mx_data)
        if mx_doc_materials := tmp_mx_doc.getMaterials():
            first_mx_material_name = mx_doc_materials[0].getName()
        else:
            # TODO: error out
            return

        prims = self.get_all_geo_prims()
        self.apply_material_to_prims(first_mx_material_name, prims)

    def refresh_mx_file(self, mx_data, emit=True):
        for layer in self.added_layers:
            self.stage_root.subLayerPaths.remove(layer)
            self.added_layers.remove(layer)

        self.stage.GetSessionLayer().Clear()

        in_memory = os.getenv("QUILTIX_WRITE_TMP_TO_DISK", "0") == "0"
        if in_memory:
            idf = "_tmp_quiltix_graph.mtlx"
            layer = Sdf.Layer.CreateAnonymous(idf)
            cur_path = self.editor.current_filepath
            if cur_path and cur_path != "untitled":
                # allows relative filepaths
                idf = os.path.join(os.path.dirname(cur_path), "_tmp_quiltix_graph.mtlx")
                layer.identifier = idf

            idf = layer.identifier
            layer.ImportFromString(mx_data)
        else:
            tmp_mtlx_export_location = os.path.join(os.environ["TEMP"], "_tmp_quiltix_graph.mtlx")
            with open(tmp_mtlx_export_location, "w") as f:
                f.write(mx_data)

            idf = tmp_mtlx_export_location

        self.stage_root.subLayerPaths.insert(0, idf)
        self.added_layers.append(idf)

        if emit:
            # TODO: remove -- DEBUG purpose
            # tmp_usd_stage_export_location = os.path.join(os.environ["TEMP"], "matxeditor_tmp.usda")
            # self.stage_root.Export(tmp_usd_stage_export_location)
            # logger.debug(f"Refreshed mtlx: {tmp_usd_stage_export_location}")
            self.signal_stage_updated.emit()

    def update_parameter(self, qx_node, property_name, property_value):
        property_name = QxNode.get_mx_input_name_from_property_name(qx_node, property_name)

        if not self.applied_material:
            return
        
        if qx_node.type_ == "Other.QxGroupNode":
            ng_name = qx_node.name()
            sub_graph = qx_node.get_sub_graph()
            if not sub_graph:
                return

            in_port_node = sub_graph.get_input_port_nodes()[0]
            out_port = in_port_node.get_output(property_name)
            cports = out_port.connected_ports()
            if not cports:
                return

            mx_stage_path = f"/MaterialX/NodeGraphs/{ng_name}/" + cports[0].node().name()
            property_name = cports[0].name()
            prim = self.stage.GetPrimAtPath(mx_stage_path)
        elif qx_node.current_mx_def.getNodeGroup() in ["material", "pbr", "shader"]:
            mat_prim = self.stage.GetPrimAtPath("/MaterialX/Materials")
            prim = mat_prim.GetChildren()[0]
            mx_stage_path = prim.GetPath().pathString
        else:
            if qx_node.graph.is_root:
                ng_name = "NG_main"
            else:
                ng_name = qx_node.graph.node.name()

            mx_stage_path = f"/MaterialX/NodeGraphs/{ng_name}/" + qx_node.NODE_NAME
            prim = self.stage.GetPrimAtPath(mx_stage_path)

        if not prim.IsValid():
            logger.warning("invalid prim at path: " + mx_stage_path)
            return

        usdinput = UsdShade.Shader(prim).GetInput(property_name)
        attr = usdinput.GetAttr()
        if not attr.IsValid():
            logger.warning(f"Invalid attribute {property_name} on prim {mx_stage_path}")
            return

        if type(property_value) in [list, tuple]:
            if len(property_value) == 4:
                property_value = property_value[
                    :3
                ]  # temporary fix, the RGB color picker widgets emits a list of 4 values

            if len(property_value) == 3:
                property_value = Gf.Vec3f(property_value)
            elif len(property_value) == 2:
                property_value = Gf.Vec2f(property_value)                

        usdinput.GetAttr().Set(property_value)
        self.signal_stage_updated.emit()

    def apply_material_to_prims(self, material_name, prims):
        mx_material_stage_path = "/".join(("", "MaterialX", "Materials", material_name))
        if not self.stage.GetPrimAtPath(mx_material_stage_path).IsValid():
            logger.warning("invalid material: " + mx_material_stage_path)
            return

        material = UsdShade.Material.Get(self.stage, mx_material_stage_path)
        prev_target = self.stage.GetEditTarget()
        self.stage.SetEditTarget(Usd.EditTarget(self._assignments_layer))
        for prim in prims:
            prim.ApplyAPI(UsdShade.MaterialBindingAPI)
            UsdShade.MaterialBindingAPI(prim).UnbindAllBindings()
            UsdShade.MaterialBindingAPI(prim).Bind(material)
            self.applied_material = mx_material_stage_path
            logger.info("applied material %s to %s" % (mx_material_stage_path, prim.GetPath()))

        self.stage.SetEditTarget(prev_target)
        self.signal_stage_updated.emit()

    def about_to_close(self):
        for layer in self.added_layers:
            self.stage_root.subLayerPaths.remove(layer)
            self.added_layers.remove(layer)
