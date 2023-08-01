import os
import sys
import subprocess
import webbrowser
import logging
from importlib import metadata

from Qt import QtCore, QtGui, QtWidgets  # type: ignore
from Qt.QtWidgets import (  # type: ignore
    QAction,
    QActionGroup,
    QMenu,
    QDockWidget,
    QMainWindow,
    QFileDialog,
    QApplication,
    QTextEdit,
    QMessageBox,
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
    QGridLayout,
    QSizePolicy,
)

from pxr import UsdShade, Usd
import MaterialX as mx

from QuiltiX import usd_stage
from QuiltiX import usd_stage_tree
from QuiltiX import usd_stage_view
from QuiltiX import qx_node
from QuiltiX import mx_node
from QuiltiX.constants import ROOT
from QuiltiX.qx_node_property import PropertiesBinWidget
from QuiltiX.qx_nodegraph import QxNodeGraph


logging.basicConfig()
logging.root.setLevel("DEBUG")
logger = logging.getLogger(__name__)


class QuiltiXWindow(QMainWindow):
    def __init__(self, load_style_sheet=True, load_shaderball=True, load_default_graph=True):
        super(QuiltiXWindow, self).__init__()
        self._version = self.get_version_string()
        self.current_filepath = ""
        self.mx_selection_path = ""
        self.geometry_selection_path = ""
        self.hdri_selection_path = ""
        self.viewer_enabled = True
        self.stage_ctrl = usd_stage.MxStageController(self)

        quiltix_logo_path = os.path.join(ROOT, "resources", "icons", "quiltix-logo-x.png")
        quiltix_icon = QtGui.QIcon(QtGui.QPixmap(quiltix_logo_path))
        self.setWindowIcon(quiltix_icon)
        self.init_ui()
        self.init_menu_bar()

        if load_style_sheet:
            self.loadStylesheet()

        self.register_qx_nodes()
        self.set_current_filepath()

        if load_shaderball:
            self.load_shaderball()

        if load_default_graph:
            self.load_default_graph()

    @classmethod
    def get_version_string(cls):
        try:
            return str(metadata.version("QuiltiX"))
        except metadata.PackageNotFoundError:
            logger.warning("Failed to get version for QuiltiX. QuiltiX is not available as package.")
            return ""

    def load_default_graph(self):
        mx_file = os.path.join(
            ROOT,
            "resources",
            "materials",
            "standard_surface.mtlx"
        )
        if not os.path.exists(mx_file):
            return

        self.qx_node_graph.load_graph_from_mx_file(mx_file)

    def load_shaderball(self):
        stage_file = os.path.join(ROOT, "resources", "geometry", "matx_shaderball_uv.usdc")
        stage = usd_stage.get_stage_from_file(stage_file)
        self.stage_ctrl.set_stage(stage)

    def init_ui(self):
        self.resize(1600, 900)
        self.setObjectName("MainWindow")
        self.l_status = QLabel()
        self.l_status.setStyleSheet("border: 0px;")
        self.statusBar().setHidden(False)
        self.statusBar().addWidget(self.l_status)

        self.setCorner(QtCore.Qt.TopRightCorner, QtCore.Qt.RightDockWidgetArea)
        self.setCorner(QtCore.Qt.TopLeftCorner, QtCore.Qt.LeftDockWidgetArea)
        self.setDockOptions(QMainWindow.AllowNestedDocks | QMainWindow.AllowTabbedDocks)

        # region Qx Node Graph
        self.qx_node_graph = QxNodeGraph()
        self.qx_node_graph_widget = self.qx_node_graph.widget
        self.qx_node_factory = self.qx_node_graph.node_factory
        self.available_qx_nodes = self.qx_node_factory.nodes
        self.qx_node_graph.set_context_menu_from_file(os.path.dirname(__file__) + "/hotkeys/hotkeys.json")
        node_menu = self.qx_node_graph.context_nodes_menu()
        self.apply_surf_mat_all_cmd = node_menu.add_command(
            "Apply to all prims",
            lambda: self.apply_material("surface", selection=False),
            node_type="Material.Surfacematerial",
        )
        self.apply_surf_mat_sel_cmd = node_menu.add_command(
            "Apply to selected prim",
            lambda: self.apply_material("surface", selection=True),
            node_type="Material.Surfacematerial",
        )
        self.apply_vol_mat__all_cmd = node_menu.add_command(
            "Apply to all prims",
            lambda: self.apply_material("volume", selection=False),
            node_type="Material.Volumematerial",
        )
        self.apply_vol_mat_sel_cmd = node_menu.add_command(
            "Apply to selected prim",
            lambda: self.apply_material("volume", selection=True),
            node_type="Material.Volumematerial",
        )
        self.save_def_cmd = node_menu.add_command(
            "Save as new definition...",
            self.save_as_definition,
            node_type="Other.QxGroupNode",
        )

        self.qx_node_graph_widget.setStyleSheet("")
        # endregion Qx Node Graph

        # region Stage Tree
        self.stage_tree_widget = self.get_stage_tree_widget()
        self.stage_tree_dock_widget = QDockWidget()
        self.stage_tree_dock_widget.setWindowTitle("Scenegraph")
        self.stage_tree_dock_widget.setWidget(self.stage_tree_widget)
        self.stage_tree_dock_widget.setAllowedAreas(QtCore.Qt.AllDockWidgetAreas)
        self.addDockWidget(QtCore.Qt.TopDockWidgetArea, self.stage_tree_dock_widget)
        # endregion Stage Tree

        # region Stage View
        if self.viewer_enabled:
            self.stage_view_widget = self.get_stage_view_widget()
            self.stage_view_widget.fileDropped.connect(self.on_view_file_dropped)
            self.stage_view_dock_widget = QDockWidget()
            self.stage_view_dock_widget.setWindowTitle("Viewport")
            self.stage_view_dock_widget.setWidget(self.stage_view_widget)
            self.stage_view_dock_widget.setAllowedAreas(QtCore.Qt.AllDockWidgetAreas)
            self.addDockWidget(QtCore.Qt.TopDockWidgetArea, self.stage_view_dock_widget)
        # endregion Stage View

        # region Properties
        self.properties = PropertiesBinWidget(root_node_graph=self.qx_node_graph)
        self.properties_dock_widget = QDockWidget()
        self.properties_dock_widget.setWindowTitle("Properties")
        self.properties_dock_widget.setWidget(self.properties)
        self.properties_dock_widget.setAllowedAreas(QtCore.Qt.AllDockWidgetAreas)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.properties_dock_widget)
        # endregion Properties

        # region Events
        self.qx_node_graph.node_graph_changed.connect(self.on_node_graph_changed)
        self.qx_node_graph.mx_data_updated.connect(self.stage_ctrl.refresh_mx_file)
        # TODO: mx_parameter_changed should maybe emit this? This would help decouple usd_stage from qx_node
        # QxNode.get_mx_input_name_from_property_name(qx_node, property_name)
        self.qx_node_graph.mx_parameter_changed.connect(self.stage_ctrl.update_parameter)
        self.qx_node_graph.mx_file_loaded.connect(self.on_mx_file_loaded)

        if self.viewer_enabled:
            self.stage_ctrl.signal_stage_changed.connect(self.stage_view_widget.set_stage)
            self.stage_ctrl.signal_stage_updated.connect(self.stage_view_widget.view.updateGL)

        self.stage_ctrl.signal_stage_changed.connect(self.stage_tree_widget.set_stage)
        self.stage_ctrl.signal_stage_updated.connect(self.stage_tree_widget.refresh_tree)
        # endregion Events

        self.setCentralWidget(self.qx_node_graph_widget)
        self.qx_node_graph_widget.setFocus()

    def on_mx_file_loaded(self, path):
        graph_data = self.qx_node_graph.get_mx_xml_data_from_graph()
        self.stage_ctrl.refresh_mx_file(graph_data, emit=False)
        if self.act_apply_mat.isChecked():
            self.stage_ctrl.apply_first_material_to_all_prims()
        self.stage_tree_widget.refresh_tree()

        self.set_current_filepath(path)

    def on_node_graph_changed(self, nodegraph):
        if self.act_apply_mat.isChecked():
            self.stage_ctrl.apply_first_material_to_all_prims()

    def get_stage_tree_widget(self):
        return usd_stage_tree.UsdStageTreeWidget()

    def get_stage_view_widget(self):
        return usd_stage_view.StageViewWidget()

    def loadStylesheet(self):
        stylesheet_file = os.path.join(ROOT, "style.qss")
        with open(stylesheet_file, "r", errors="ignore") as f:
            stylesheet = f.read()

        stylesheet = stylesheet.replace("url(\"", "url(\"{}/".format(ROOT.replace("\\", "/")))
        self.setStyleSheet(stylesheet)

    def setStyleSheet(self, stylesheet):
        self.qx_node_graph_widget.setStyleSheet(stylesheet)
        super(QuiltiXWindow, self).setStyleSheet(stylesheet)

    def set_stage(self, stage):
        self.stage_ctrl.set_stage(stage)
        self.qx_node_graph.update_mx_xml_data_from_graph()
        self.stage_tree_widget.refresh_tree()

    def apply_material(self, mat_type, selection=False):
        if mat_type == "surface":
            if selection:
                action = self.apply_surf_mat_sel_cmd.qaction
            else:
                action = self.apply_surf_mat_all_cmd.qaction
        elif mat_type == "volume":
            if selection:
                action = self.apply_vol_mat_sel_cmd.qaction
            else:
                action = self.apply_vol_mat_all_cmd.qaction

        node = self.qx_node_graph.get_node_by_id(action.node_id)
        material_name = node.NODE_NAME
        if selection:
            prims = self.stage_tree_widget.get_selected_prims()
        else:
            prims = self.stage_ctrl.get_all_geo_prims()
            if not prims:
                return

        self.stage_ctrl.apply_material_to_prims(material_name, prims)

    def save_as_definition(self):
        action = self.save_def_cmd.qaction
        node = self.qx_node_graph.get_node_by_id(action.node_id)
        dlg_save = SaveDefinitionDialog(node, self)
        dlg_save.signal_saved_def.connect(self.on_defitintion_saved)
        dlg_save.show()

    def on_defitintion_saved(self, filepath):
        dirpath = os.path.dirname(filepath)
        if dirpath not in os.getenv("PXR_MTLX_PLUGIN_SEARCH_PATHS", "").split(os.pathsep):
            os.environ["PXR_MTLX_PLUGIN_SEARCH_PATHS"] = os.getenv("PXR_MTLX_PLUGIN_SEARCH_PATHS", "") + os.pathsep + dirpath

        self.qx_node_graph.load_mx_libraries([dirpath], library_folders=[])

    def init_menu_bar(self):
        # region Tabs
        self.file_menu = self.menuBar().addMenu("&File")
        self.options_menu = self.menuBar().addMenu("&Options")
        self.view_menu = self.menuBar().addMenu("&View")
        help_menu = self.menuBar().addMenu("&Help")
        # endregion Tabs

        # region File
        load_mx_file = QAction("Load MaterialX...", self)
        load_mx_file.triggered.connect(self.load_mx_file_triggered)
        self.file_menu.addAction(load_mx_file)

        save_mx_file = QAction("Save MaterialX...", self)
        save_mx_file.triggered.connect(self.save_mx_file_triggered)
        self.file_menu.addAction(save_mx_file)

        self.file_menu.addSeparator()

        load_geo = QAction("Load Geometry...", self)
        load_geo.triggered.connect(self.load_geometry_triggered)
        self.file_menu.addAction(load_geo)

        load_geo = QAction("Load HDRI...", self)
        load_geo.triggered.connect(self.load_hdri_triggered)
        self.file_menu.addAction(load_geo)

        self.file_menu.addSeparator()

        show_mx_text = QAction("Show MaterialX as text...", self)
        show_mx_text.triggered.connect(self.show_mx_text_triggered)
        self.file_menu.addAction(show_mx_text)

        self.file_menu.addSeparator()

        show_mx_view = QAction("Open in MaterialX View...", self)
        show_mx_view.triggered.connect(self.show_mx_view_triggered)
        self.file_menu.addAction(show_mx_view)

        show_mx_editor = QAction("Open in MaterialX Graph Editor...", self)
        show_mx_editor.triggered.connect(self.show_mx_editor_triggered)
        self.file_menu.addAction(show_mx_editor)

        show_usdview = QAction("Open in Usdview...", self)
        show_usdview.triggered.connect(self.show_usdview_triggered)
        self.file_menu.addAction(show_usdview)
        # endregion File

        # region Options
        self.act_update_ng = QAction("Auto update on nodegraph change", self)
        self.act_update_ng.setCheckable(True)
        self.act_update_ng.setChecked(True)
        self.act_update_ng.toggled.connect(lambda state: setattr(self.qx_node_graph, "auto_update_ng", state))
        self.qx_node_graph.auto_update_ng = self.act_update_ng.isChecked()
        self.options_menu.addAction(self.act_update_ng)

        self.act_update_prop = QAction("Auto update on property change", self)
        self.act_update_prop.setCheckable(True)
        self.act_update_prop.setChecked(True)
        self.act_update_prop.toggled.connect(lambda state: setattr(self.qx_node_graph, "auto_update_prop", state))
        self.options_menu.addAction(self.act_update_prop)

        self.act_apply_mat = QAction("Auto apply material to all prims", self)
        self.act_apply_mat.setCheckable(True)
        self.act_apply_mat.setChecked(True)
        self.options_menu.addAction(self.act_apply_mat)

        self.act_ng_abstraction = QAction("Auto create Nodegraph around shader inputs", self)
        self.act_ng_abstraction.setCheckable(True)
        self.act_ng_abstraction.setChecked(True)
        self.options_menu.addAction(self.act_ng_abstraction)

        self.act_validate = QAction("Validate MaterialX document...", self)
        self.act_validate.triggered.connect(self.validate)
        self.options_menu.addAction(self.act_validate)

        self.act_reload_defs = QAction("Reload Node Definitions", self)
        self.act_reload_defs.triggered.connect(self.reload_defs)
        self.options_menu.addAction(self.act_reload_defs)
        # endregion Options

        # region View
        if self.viewer_enabled:
            self.menu_set_current_renderer = QMenu("&Set Renderer", self)
            self.grp_set_current_renderer = QActionGroup(self, exclusive=True)
            self.grp_set_current_renderer.triggered.connect(
                lambda action: self.stage_view_widget.set_current_renderer_by_name(action.text())
            )
            self.menu_set_current_renderer.aboutToShow.connect(self.on_set_renderer_menu_showing)
            self.view_menu.addMenu(self.menu_set_current_renderer)

            self.act_hdri = QAction("Enable HDRI", self)
            self.act_hdri.setCheckable(True)
            self.act_hdri.setChecked(True)
            self.act_hdri.toggled.connect(self.stage_view_widget.set_hdri_enabled)
            self.act_hdri.toggled.connect(lambda x: self.stage_tree_widget.refresh_tree())
            self.view_menu.addAction(self.act_hdri)
            self.view_menu.addSeparator()

        self.view_menu.aboutToShow.connect(self.on_view_menu_showing)
        self.act_prop = QAction("Properties", self)
        self.act_prop.setCheckable(True)
        self.act_prop.toggled.connect(self.on_properties_toggled)
        self.view_menu.addAction(self.act_prop)

        self.act_scenegraph = QAction("Scenegraph", self)
        self.act_scenegraph.setCheckable(True)
        self.act_scenegraph.toggled.connect(self.on_scenegraph_toggled)
        self.view_menu.addAction(self.act_scenegraph)

        self.act_viewport = QAction("Viewport", self)
        self.act_viewport.setCheckable(True)
        self.act_viewport.toggled.connect(self.on_viewport_toggled)
        if self.viewer_enabled:
            self.view_menu.addAction(self.act_viewport)
        # endregion View

        # region About
        # endregion About

        # region Help
        mx_homepage = QAction("MaterialX Homepage...", self)
        mx_homepage.triggered.connect(self.open_mx_homepage_triggered)
        help_menu.addAction(mx_homepage)

        mx_spec = QAction("Node Definitions...", self)
        mx_spec.triggered.connect(self.open_mx_spec_triggered)
        help_menu.addAction(mx_spec)

        homepage_action = QAction("QuiltiX Homepage...", self)
        homepage_url = "https://github.com/prismpipeline/QuiltiX/"
        homepage_action.triggered.connect(lambda: webbrowser.open(homepage_url))
        help_menu.addAction(homepage_action)

        issues_action = QAction("QuiltiX issues...", self)
        issues_url = "https://github.com/prismpipeline/QuiltiX/issues"
        issues_action.triggered.connect(lambda: webbrowser.open(issues_url))
        help_menu.addAction(issues_action)

        versions_to_be_displayed = [
            f"USD version:       v{'.'.join([str(i) for i in Usd.GetVersion()])}",
            f"MaterialX version: v{mx.getVersionString()}",
        ]
        versions_submenu = QMenu("Loaded Versions", self)
        for version in versions_to_be_displayed:
            version_action = QAction(version, self)
            version_action.setEnabled(False)
            versions_submenu.addAction(version_action)

        help_menu.addMenu(versions_submenu)

        about_action = QAction("About QuiltiX", self)
        about_action.triggered.connect(self.show_about_triggered)
        help_menu.addAction(about_action)
        # endregion Help

        # region Update
        update_icon = QtGui.QIcon(os.path.join(ROOT, "resources", "icons", "update.svg"))
        self.act_update = QAction(update_icon, "", self)
        self.act_update.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F5))
        self.menuBar().addAction(self.act_update)
        self.act_update.triggered.connect(self.qx_node_graph.update_mx_xml_data_from_graph)
        # endregion Update

    def on_view_menu_showing(self):
        self.act_prop.setChecked(self.properties_dock_widget.isVisible())
        self.act_scenegraph.setChecked(self.stage_tree_dock_widget.isVisible())
        if self.viewer_enabled:
            self.act_viewport.setChecked(self.stage_view_dock_widget.isVisible())

    def on_set_renderer_menu_showing(self):
        # We add the available renderers on demand, since they are not available before the
        # ui finished rendering for the first time

        current_renderer_name = self.stage_view_widget.get_current_renderer_name()
        if self.menu_set_current_renderer.actions():
            # We already determined the renderers and just make sure the right one is checked
            for act in self.menu_set_current_renderer.actions():
                if act.text() == current_renderer_name:
                    act.setChecked(True)
                    return
            return

        for renderer_name in self.stage_view_widget.get_available_renderer_plugin_names():
            act_renderer = QAction(renderer_name, self)
            act_renderer.setCheckable(True)
            if renderer_name == current_renderer_name:
                act_renderer.setChecked(True)
            self.grp_set_current_renderer.addAction(act_renderer)

        self.menu_set_current_renderer.addActions(self.grp_set_current_renderer.actions())

    def load_mx_file_triggered(self):
        start_path = self.mx_selection_path
        if not start_path:
            start_path = self.geometry_selection_path

        if not start_path:
            start_path = os.path.join(ROOT, "resources", "materials")

        path = self.request_filepath(
            title="Open MaterialX file",
            start_path=start_path,
            file_filter="MaterialX files (*.mtlx)",
            mode="open",
        )
        if not path:
            return

        self.mx_selection_path = path
        self.qx_node_graph.load_graph_from_mx_file(path)

    def save_mx_file_triggered(self):
        start_path = self.mx_selection_path
        if not start_path:
            start_path = self.geometry_selection_path

        if not start_path:
            start_path = os.path.join(ROOT, "resources", "materials")

        path = self.request_filepath(
            title="Save MaterialX file", start_path=start_path, file_filter="MaterialX files (*.mtlx)", mode="save"
        )
        if not path:
            return

        self.mx_selection_path = path
        self.qx_node_graph.save_graph_as_mx_file(path)
        self.set_current_filepath(path)

    def set_current_filepath(self, path=None):
        path = path or "untitled"
        self.current_filepath = path
        self.setWindowTitle(f"QuiltiX v{self._version} - {path}")

    def show_mx_text_triggered(self):
        text = self.qx_node_graph.get_mx_xml_data_from_graph()
        te_text = QTextEdit()
        te_text.setText(text)
        te_text.setReadOnly(True)
        te_text.setParent(self, QtCore.Qt.Window)
        te_text.setWindowTitle("MaterialX text preview")
        te_text.resize(1000, 800)
        te_text.show()

    def show_mx_view_triggered(self):
        exe = os.getenv("MATERIALX_VIEW", "")
        if not os.path.exists(exe):
            QMessageBox.warning(self, "Warning", 'Environment variable "MATERIALX_VIEW" is not set.')
            return

        mx_data = self.qx_node_graph.get_mx_xml_data_from_graph()
        tmp_mtlx_export_location = os.path.join(os.environ["TEMP"], "_tmp_quiltix.mtlx")
        with open(tmp_mtlx_export_location, "w") as f:
            f.write(mx_data)

        subprocess.Popen([exe, "--material", tmp_mtlx_export_location])

    def show_mx_editor_triggered(self):
        exe = os.getenv("MATERIALX_EDITOR", "")
        if not os.path.exists(exe):
            QMessageBox.warning(self, "Warning", 'Environment variable "MATERIALX_EDITOR" is not set.')
            return

        mx_data = self.qx_node_graph.get_mx_xml_data_from_graph()
        tmp_mtlx_export_location = os.path.join(os.environ["TEMP"], "_tmp_quiltix.mtlx")
        with open(tmp_mtlx_export_location, "w") as f:
            f.write(mx_data)

        args = [exe, "--material", tmp_mtlx_export_location]
        mx_custom_lib_paths = mx_node.get_mx_custom_lib_paths()
        for path in mx_custom_lib_paths:
            args += ["--library", path]

        subprocess.Popen(args)

    def show_usdview_triggered(self):
        usdview_path = os.getenv("USDVIEW", "")
        if not os.path.exists(usdview_path):
            QMessageBox.warning(self, "Warning", 'Environment variable "USDVIEW" is not set.')
            return

        tmp_usd_stage_export_location = os.path.join(os.environ["TEMP"], "_tmp_quiltix.usda")
        self.stage_ctrl.stage.Export(tmp_usd_stage_export_location)
        executable = sys.executable
        if "QuiltiX" in os.path.basename(executable):
            executable = os.path.join(os.path.dirname(executable), "python.exe")

        subprocess.Popen([executable, usdview_path, tmp_usd_stage_export_location])

    def show_about_triggered(self):
        message_box = QtWidgets.QMessageBox()

        message_box_texts = [
            f"<p>Version: {self._version}<p><p>&nbsp;</p>",
            "<p><a href='https://github.com/PrismPipeline/QuiltiX' style='color:#ffffff;'>Homepage...</a></p>",
            "<p><a href='https://github.com/prismpipeline/QuiltiX/LICENSE' style='color:#ffffff;'>License...</a></p>",
            "<p>© Manuel Köster and Richard Frangenberg</p>"
        ]
        message_box_text = "".join(message_box_texts)
        message_box.setTextFormat(QtCore.Qt.RichText)
        message_box.about(self, 'About QuiltiX', message_box_text)

    def on_view_file_dropped(self, filepath):
        base, ext = os.path.splitext(filepath)
        if ext in [".hdr", ".hdri", ".exr", ".jpg", ".png"]:
            self.stage_view_widget.set_hdri(filepath)
            self.stage_tree_widget.refresh_tree()
        elif ext in [".usd", ".usda", ".usdc"]:
            loaded_stage = usd_stage.get_stage_from_file(filepath)
            self.set_stage(loaded_stage)
            # self.fix_geo(self.stage_tree_widget.invisibleRootItem())

    def load_geometry_triggered(self):
        start_path = self.geometry_selection_path
        if not start_path:
            start_path = self.mx_selection_path

        if not start_path:
            start_path = os.path.join(ROOT, "resources", "geometry")

        path = self.request_filepath(
            title="Load geometry file",
            start_path=start_path,
            file_filter="Geometry files (*.usd *.usda *.usdc *.abc)",
        )
        if not path:
            return

        self.geometry_selection_path = path
        loaded_stage = usd_stage.get_stage_from_file(path)
        self.set_stage(loaded_stage)
        # self.fix_geo(self.stage_tree_widget.invisibleRootItem())

    def load_hdri_triggered(self):
        start_path = self.hdri_selection_path
        if not start_path:
            start_path = self.mx_selection_path

        if not start_path:
            start_path = os.path.join(ROOT, "resources", "hdris")

        path = self.request_filepath(
            title="Load HDRI file",
            start_path=start_path,
            file_filter="Image files (*.hdr *.hdri *.exr *.jpg *.png *.tif *.tiff)",
        )
        if not path:
            return

        self.hdri_selection_path = path
        self.stage_view_widget.set_hdri(path)
        self.stage_tree_widget.refresh_tree()

    def on_properties_toggled(self, checked):
        self.properties_dock_widget.setVisible(checked)

    def on_scenegraph_toggled(self, checked):
        self.stage_tree_dock_widget.setVisible(checked)

    def on_viewport_toggled(self, checked):
        self.stage_view_dock_widget.setVisible(checked)

    def open_mx_homepage_triggered(self):
        url = "https://www.materialx.org"
        webbrowser.open(url)

    def open_mx_spec_triggered(self):
        mx_major_minor_version = '.'.join([str(i) for i in mx.getVersionIntegers()[:2]])
        url = f"https://www.materialx.org/assets/MaterialX.v{mx_major_minor_version}.Spec.pdf"
        webbrowser.open(url)

    def register_qx_nodes(self):
        mx_stdlib_paths = mx_node.get_mx_stdlib_paths()
        self.qx_node_graph.load_mx_libraries(mx_stdlib_paths)
        mx_custom_lib_paths = mx_node.get_mx_custom_lib_paths()
        self.qx_node_graph.load_mx_libraries(mx_custom_lib_paths, library_folders=[])
        self.qx_node_graph.register_node(qx_node.QxGroupNode)

    def validate(self, doc=None, popup=True):
        result = self.qx_node_graph.validate_mtlx_doc(doc)
        if result[0]:
            msg = popup_msg = f"Graph is valid."
            self.statusBar().setStyleSheet("QStatusBar::item {border: None}")
        else:
            msg = f"Graph is invalid:    {result[1]}".strip("\n")
            popup_msg = f"Graph is invalid:\n\n{result[1]}".strip("\n")
            self.statusBar().setStyleSheet("QStatusBar::item {border: None} QWidget {background-color: rgb(200, 30, 30);}")

        self.l_status.setText(msg)
        if popup:
            QMessageBox.information(self, "Validation", popup_msg)

    def reload_defs(self):
        self.qx_node_graph.unregister_nodes()
        self.register_qx_nodes()

    def request_filepath(
        self, title="Select File", start_path="", parent=None, file_filter="All files (*.*)", mode="open"
    ):
        if mode not in ["open", "save"]:
            raise ValueError
        parent = parent or self
        if mode == "open":
            path = QFileDialog.getOpenFileName(parent, title, start_path, file_filter)[0]
        elif mode == "save":
            path = QFileDialog.getSaveFileName(parent, title, start_path, file_filter)[0]

        return path

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_F9:
            logger.debug("Reload stylesheet")
            self.loadStylesheet()

    def closeEvent(self, event):
        if self.viewer_enabled:
            self.stage_view_widget.closeEvent(event)

        self.stage_ctrl.about_to_close()

    def fix_geo(self, item, emit=True):
        if hasattr(item, "prim"):
            prim = item.prim

            # prim.ApplyAPI(UsdShade.MaterialBindingAPI)
            UsdShade.MaterialBindingAPI(prim).UnbindAllBindings()
            attr = prim.GetAttribute("primvars:st0")
            if attr:
                attr.GetPropertyStack(0)[0].name = "primvars:st"

        for idx in range(item.childCount()):
            self.fix_geo(item.child(idx), emit=False)

        if emit:
            self.stage_ctrl.signal_stage_changed.emit()


class SaveDefinitionDialog(QDialog):

    signal_saved_def = QtCore.Signal(object)

    def __init__(self, node, parent):
        super(SaveDefinitionDialog, self).__init__(parent)
        self.node = node
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Save Node Definition")

        self.l_category = QLabel("Category:")
        self.e_category = QLineEdit("Custom")
        self.l_name = QLabel("Name:")
        self.e_name = QLineEdit(self.node.NODE_NAME)
        self.l_path = QLabel("Save Path:   ")
        path = os.path.join(os.environ["USERPROFILE"], "custom_mtlx_defs", self.node.NODE_NAME + ".mtlx")
        self.e_path = QLineEdit(path)
        self.b_path = QPushButton("...")
        self.bb_main = QDialogButtonBox()
        self.bb_main.addButton("Save", QDialogButtonBox.AcceptRole)
        self.bb_main.addButton("Cancel", QDialogButtonBox.RejectRole)

        self.bb_main.accepted.connect(self.on_accepted)
        self.bb_main.rejected.connect(self.reject)

        self.e_category.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.lo_main = QGridLayout(self)
        self.lo_main.addWidget(self.l_category, 0, 0)
        self.lo_main.addWidget(self.e_category, 0, 1, 1, 3)
        self.lo_main.addWidget(self.l_name, 1, 0)
        self.lo_main.addWidget(self.e_name, 1, 1, 1, 3)
        self.lo_main.addWidget(self.l_path, 2, 0)
        self.lo_main.addWidget(self.e_path, 2, 1, 1, 2)
        self.lo_main.addWidget(self.b_path, 2, 3)
        self.lo_main.setRowStretch(3, 100)
        self.lo_main.setColumnStretch(1, 100)
        self.lo_main.addWidget(self.bb_main, 4, 2, 1, 2)
        self.e_name.setFocus()

    def sizeHint(self):
        return QtCore.QSize(580, 175)

    def on_accepted(self):
        nodegroup = self.e_category.text()
        if not nodegroup:
            QMessageBox.warning(self, "Warning", "Invalid category.")
            return

        nodename = self.e_name.text()
        if not nodegroup:
            QMessageBox.warning(self, "Warning", "Invalid name.")
            return

        outpath = self.e_path.text()
        if not outpath.endswith(".mtlx"):
            QMessageBox.warning(self, "Warning", "Invalid Save Path.")
            return

        node_name = self.node.NODE_NAME
        doc = mx.createDocument()

        graph_doc = mx.createDocument()
        graph_data = self.node.graph.get_current_graph_data()
        graph_data["nodes"] = {self.node.id: graph_data["nodes"][self.node.id]}
        graph_data["connections"] = []
        graph_doc = self.node.graph.get_mx_doc_from_serialized_data(graph_data, mx_parent=graph_doc)
        ng = graph_doc.getNodeGraphs()[0]

        version = "1.0.0"
        defaultversion = False
        nodedefName = 'ND_' + nodename
        nodegraphName = 'NG_' + nodename  # not working?
        ng.setName(nodegraphName)

        definition = doc.addNodeDefFromGraph(
            ng,
            nodedefName,
            nodename,
            version,
            defaultversion,
            nodegroup,
            nodegraphName
        )
        ng = doc.getNodeGraph(nodegraphName)

        for ng_input in ng.getInputs():
            ndef_input = definition.addInput(ng_input.getName(), ng_input.getType())
            if ndef_input:
                ndef_input.copyContentFrom(ng_input)
                ndef_input.setSourceUri('')

        defDoc = mx.createDocument()
        newDef = defDoc.addNodeDef(definition.getName(), '', definition.getCategory())
        newDef.copyContentFrom(definition)
        newGraph = defDoc.addNodeGraph(ng.getName())
        newGraph.copyContentFrom(ng)

        outdir = os.path.dirname(outpath)
        if not os.path.exists(outdir):
            os.makedirs(outdir)

        mx.writeToXmlFile(defDoc, outpath)
        if os.path.exists(outpath):
            logger.info(f"saved node definition to {outpath}")
        else:
            logger.warning(f"failed to save node definition to {outpath}")

        self.accept()
        self.signal_saved_def.emit(outpath)


def launch():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    # signal.signal(signal.SIGINT, signal.SIG_DFL)
    editor = QuiltiXWindow()
    editor.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    launch()
