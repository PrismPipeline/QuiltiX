import os
import re
import logging
import copy
from contextlib import contextmanager

import NodeGraphQt
from NodeGraphQt.nodes.group_node import GroupNode
from qtpy import QtCore, QtGui, QtWidgets  # type: ignore
from QuiltiX.qx_nodegraph_viewer import QxNodeGraphViewer  

import QuiltiX.qx_node as qx_node_module
from QuiltiX import constants

import MaterialX as mx  # type: ignore


logger = logging.getLogger(__name__)


class QxNodeGraph(NodeGraphQt.NodeGraph):
    """
    Signal triggered when a node inside the nodegraph type has been changed.

    :parameters: str
    :emits: node_id of the changed node.
    """

    # str : path of mtlx file
    # bool : refresh needed
    mx_data_updated = QtCore.Signal(str, bool)
    mx_parameter_changed = QtCore.Signal(object, object, object)
    mx_file_loaded = QtCore.Signal(object)
    potentially_node_graph_changed = QtCore.Signal(object)
    node_graph_changed = QtCore.Signal(object)

    def __init__(self, parent=None, node_factory=None, **kwargs):
        kwargs["viewer"] = kwargs.get("viewer") or QxNodeGraphViewer(self)
        super(QxNodeGraph, self).__init__(parent, node_factory=node_factory, **kwargs)
        if self._undo_stack:
            self._viewer._undo_action = self._undo_stack.createUndoAction(self, '&Undo')
            self._viewer._redo_action = self._undo_stack.createRedoAction(self, '&Redo')

        self._block_save = False
        self.auto_update_ng = False
        self.auto_update_prop = True
        self.copy_to_ng_cmds = {}
        self.node_created.connect(self.on_node_created)
        self.nodes_deleted.connect(self.on_nodes_deleted)
        self.property_changed.connect(self.on_property_changed)
        self.port_connected.connect(self.on_port_connected)
        self.port_disconnected.connect(self.on_port_disconnected)
        self.mx_file_loaded.connect(self.on_mx_file_loaded)
        self.potentially_node_graph_changed.connect(self.on_potentially_node_graph_changed)
        self.node_graph_changed.connect(self.on_node_graph_changed)

        # Initialize mx containers
        # The library document holds all the node definitions loaded and available for the nodegraph
        self.mx_library_doc = mx.createDocument()
        # The mx definitions available for the nodegraphself._realtime_update
        self.mx_defs = None
        # Keeping track what node graph we are currently in
        self.current_node_graph = self

    @property
    def subnodegraph_class(self):
        from QuiltiX.qx_subnodegraph import QxSubNodeGraph
        return QxSubNodeGraph

    @contextmanager
    def block_save(self):
        self._block_save = True
        yield
        self._block_save = False

    # custom start - added function
    def get_root_graph(self, node_graph=None):
        if not node_graph:
            node_graph = self

        if node_graph.is_root:
            return node_graph
        else:
            return self.get_root_graph(node_graph.parent_graph)
    # custom end

    def on_potentially_node_graph_changed(self, node_graph):
        root_graph = self.get_root_graph()
        if node_graph == root_graph.get_root_graph().current_node_graph:
            return

        root_graph.node_graph_changed.emit(node_graph)

    def on_node_graph_changed(self, node_graph):
        self.current_node_graph = node_graph
        logger.debug("graph_changed" + str(self.current_node_graph))

    def _on_node_selected(self, node_id):
        logger.debug("node_selected" + str(self))
        self.potentially_node_graph_changed.emit(self)
        super()._on_node_selected(node_id)

    def load_mx_libraries(self, search_paths=None, library_folders=None, library_path=None, add_to_lib_doc=True):
        if search_paths is None:
            search_paths = []

        if library_folders is None:
            library_folders = []

        if add_to_lib_doc:
            doc = self.mx_library_doc
        else:
            doc = mx.createDocument()
            doc.importLibrary(self.mx_library_doc)

        for search_path in search_paths:
            mx_search_path = mx.FileSearchPath(search_path)
            defs = mx.loadLibraries(library_folders, mx_search_path, doc)
            logger.debug(f"loaded definitions from {search_path}: {len(defs)}")

        if library_path:
            mx.loadLibrary(library_path, doc)
            logger.debug(f"loaded definitions from {library_path}")

        if self.mx_defs:
            mx_defs = [mx_def for mx_def in doc.getNodeDefs() if mx_def not in self.mx_defs]
        else:
            mx_defs = doc.getNodeDefs()

        new_defs = []
        if mx_defs:
            new_defs = qx_node_module.qx_node_from_mx_node_group_dict_generator(mx_defs)
            self.register_nodes(new_defs)

            node_menu = self.context_nodes_menu()
            for mx_def in mx_defs:
                if self.has_nodegraph_implementation(mx_def):
                    
                    node_type = f"{mx_def.getNodeGroup().capitalize()}.{mx_def.getNodeString().capitalize()}"
                    if not node_menu.qmenu.get_menu(node_type):
                        self.copy_to_ng_cmds[node_type] = node_menu.add_command(
                            "Copy to Nodegraph",
                            self.copy_to_node_graph,
                            node_type=node_type,
                        )

        self.mx_defs = doc.getNodeDefs()
        return new_defs

    def has_nodegraph_implementation(self, mx_def):
        imp = mx_def.getImplementation()
        if not imp:
            return False

        if isinstance(imp, mx.NodeGraph):
            return True

        ng_name = imp.getAttribute("nodegraph")
        if ng_name:
            return True
        else:
            return False

    def copy_to_node_graph(self, graph, node):
        with self.get_root_graph().block_save():
            imp = node.current_mx_def.getImplementation()
            if isinstance(imp, mx.NodeGraph):
                ng = imp
            else:
                ng_name = imp.getAttribute("nodegraph")
                ng = self.mx_library_doc.getNodeGraph(ng_name)

            pos = [node.x_pos(), node.y_pos() + node.view.height + 10]
            ng_node = self.create_nodegraph_from_mx_nodegraph(ng, pos=pos, create_ports=False)
            for output in node.current_mx_def.getActiveOutputs():
                color = qx_node_module.QxNodeBase._random_color_from_string(str(output.getType()))
                ng_node.add_output(output.getName(), color=color)

            for minput in node.current_mx_def.getActiveInputs():
                qx_node_module.QxNode.create_property_from_mx_input(minput, ng_node)
                color = qx_node_module.QxNodeBase._random_color_from_string(str(minput.getType()))
                in_port = ng_node.add_input(minput.getName(), color=color)
                in_port.view.setToolTip(minput.getType())

            qx_node_to_mx_node = {}
            had_pos = False
            for cur_mx_node in ng.getNodes():
                if cur_mx_node.hasAttribute("xpos") and cur_mx_node.hasAttribute("ypos"):
                    had_pos = True

                cur_qx_node = self.create_node_from_mx_node(cur_mx_node, graph=ng_node.get_sub_graph())
                # Change value type of node
                qx_node_to_mx_node[cur_qx_node] = cur_mx_node

            for cur_qx_node, cur_mx_node in qx_node_to_mx_node.items():
                cur_qx_node.graph.connect_qx_inputs_from_mx_node(cur_qx_node, cur_mx_node)

            self.connect_qx_ng_ports_from_mx_ng(ng_node, ng, node.current_mx_def)
            # graphs = [self.get_root_graph()]
            # graphs += list(self.sub_graphs.values())
            # for graph in graphs:
            if not had_pos:
                ng_node.get_sub_graph().auto_layout_nodes()

            self.collapse_group_node(ng_node)

    def unregister_nodes(self):
        self._node_factory.clear_registered_nodes()
        self.mx_library_doc = mx.createDocument()
        self.mx_defs = None
        self._viewer.rebuild_tab_search()

    def on_port_connected(self, input_port, output_port):
        # FIXME: fix auto type conversion
        # if type(input_port).__name__ != "QxPortItem" or type(output_port).__name__ != "QxPortItem":
        # if type(input_port).__name__ != "Port" or type(output_port).__name__ != "Port":
        #     return

        # if type(input_port).__name__ == "QxPortItem":
        #     input_port_type = input_port.view.get_port_types(current=True)
        # else:
        #     input_port_type = ""

        # if type(output_port).__name__ == "QxPortItem":
        #     output_port_type = output_port.view.get_port_types(current=True)
        # else:
        #     output_port_type = ""

        if not self.is_root:
            self.get_root_graph().on_port_connected(input_port, output_port)
            return

        if self.get_root_graph().auto_update_ng:
            self.update_mx_xml_data_from_graph()
            return
        # if self.viewer()._start_port.node == input_port.node():
        #     # start_port = input_port
        #     start_port_type = input_port_type
        #     # end_port = output_port
        #     end_port_type = output_port_type
        # else:
        #     # start_port = output_port
        #     start_port_type = output_port_type
        #     # end_port = input_port
        #     end_port_type = input_port_type

        # if end_port_type in qx_port.ADDITIONAL_COMPATIBLE_PORT_TYPES and \
        #         start_port_type in qx_port.ADDITIONAL_COMPATIBLE_PORT_TYPES[end_port_type]:
        #     # we don't need to change
        #     if self.auto_update_ng:
        #         self.update_mx_xml_data_from_graph()
        #         return

        # if input_port_type != output_port_type:
        #     changed = self.match_port_types(input_port, output_port)
        #     if changed:
        #         return

        # if self.auto_update_ng:
        #     self.update_mx_xml_data_from_graph()

    def match_port_types(self, input_port, output_port):
        input_node = input_port.node()
        output_node = output_port.node()
        input_name = input_port.name()
        output_name = output_port.name()
        input_type = input_port.type_()
        intypes = input_port.view.get_port_types()
        outtypes = output_port.view.get_port_types()

        for intype in intypes:
            if intype in outtypes:
                if intype != input_port.view.get_port_types(current=True):
                    input_node.change_type(intype)

                if intype != output_port.view.get_port_types(current=True):
                    output_node.change_type(intype)

                if input_type == "in":
                    input_node.inputs()[input_name].connect_to(output_node.outputs()[output_name])
                else:
                    input_node.outputs()[input_name].connect_to(output_node.inputs()[output_name])

                return True

    def on_node_created(self, qx_node):
        # Only if a mx node with possible types (eg not a group node)
        logger.debug("created_node " + str(qx_node))
        if not self.get_root_graph()._block_save:
            self.potentially_node_graph_changed.emit(self)

        qx_node._view.basenode = qx_node
        if isinstance(qx_node, NodeGraphQt.BackdropNode):
            return

        for nodeInput in qx_node.input_ports():
            if hasattr(nodeInput._Port__view, "refresh_tool_tip"):
                nodeInput._Port__view.refresh_tool_tip()

        for nodeOutput in qx_node.output_ports():
            if hasattr(nodeOutput._Port__view, "refresh_tool_tip"):
                nodeOutput._Port__view.refresh_tool_tip()

        # If the the node is created from the live connection tab menu we want to try to match the port types
        port_to_connect = getattr(self.viewer()._search_widget, "port_to_connect", None)
        if not port_to_connect:
            return

        # Skip if the created node is a group node which does not have types -> no type change needed
        if qx_node.type_ == "Other.QxGroupNode":
            return

        # Skip if the created node does not have opposing ports -> no type change needed
        ports = qx_node.outputs() if port_to_connect.port_type == "in" else qx_node.inputs()
        if not ports:
            return

        node_to_connect = self.get_node_by_id(port_to_connect.node.id)
        target_port = next(iter(ports.values()))

        if port_to_connect.port_type == "in":
            source_port = node_to_connect.inputs()[port_to_connect.name]
        else:
            source_port = node_to_connect.outputs()[port_to_connect.name]

        if hasattr(source_port.view, "get_mx_port_type"):
            source_port_type = source_port.view.get_mx_port_type()
            target_port_type = target_port.view.get_mx_port_type()
            if source_port_type != target_port_type:
                mx_def_name = qx_node.get_mx_def_name_from_data_type(source_port_type, target_port.type_())

                qx_node.change_type(mx_def_name)

        if port_to_connect.port_type == "in":
            node_port = qx_node.output_ports()[0]
        else:
            node_port = qx_node.input_ports()[0]

        node_port.connect_to(source_port)
        delta = qx_node._view.scenePos() - node_port._Port__view.scenePos()
        new_pos = qx_node._view.scenePos() + delta
        qx_node.set_pos(new_pos.x(), new_pos.y())
        QtWidgets.QApplication.processEvents()

    def on_nodes_deleted(self, node_ids):
        self.has_deleted_nodes = True

    def on_property_changed(self, qx_node, property_name, property_value):
        logger.debug(f"property changed {property_name} - {property_value}")
        disregarded_properties = ["pos", "color", "width", "height", "selected"]
        if property_name in disregarded_properties:
            return

        if property_name == "type":
            qx_node.change_type(property_value)
            if qx_node.selected():
                # this will update the property bin
                self.node_selected.emit(qx_node)

        if qx_node.type_ in ["Outputs.QxPortOutputNode"]:
            portnum = int(property_name.replace("Output #", ""))
            port = qx_node.input(portnum-1)
            port.model.name = property_value
            port.view.name = property_value
            text_item = qx_node.view.get_input_text_item(port.view)
            text_item.setPlainText(property_value)
            qx_node.model.inputs[property_value] = port.model

            port = qx_node.graph.node.output(portnum-1)
            port.model.name = property_value
            port.view.name = property_value
            text_item = qx_node.graph.node.view.get_output_text_item(port.view)
            text_item.setPlainText(property_value)
            qx_node.graph.node.model.outputs[property_value] = port.model
        elif qx_node.type_ in ["Inputs.QxPortInputNode"]:
            portnum = int(property_name.replace("Input #", ""))
            port = qx_node.output(portnum-1)
            prev_name = port.model.name
            port.model.name = property_value
            port.view.name = property_value
            text_item = qx_node.view.get_output_text_item(port.view)
            text_item.setPlainText(property_value)
            qx_node.model.outputs[property_value] = port.model

            port = qx_node.graph.node.input(portnum-1)
            port.model.name = property_value
            port.view.name = property_value
            text_item = qx_node.graph.node.view.get_input_text_item(port.view)
            text_item.setPlainText(property_value)
            qx_node.graph.node.model.inputs[property_value] = port.model

            qx_node.graph.node.model._custom_prop[property_value] = qx_node.graph.node.model._custom_prop[prev_name]
            del qx_node.graph.node.model._custom_prop[prev_name]
            qx_node.graph.node.model._graph_model._NodeGraphModel__common_node_props[qx_node.graph.node.model.type_][property_value] = qx_node.graph.node.model._graph_model._NodeGraphModel__common_node_props[qx_node.graph.node.model.type_][prev_name]
            del qx_node.graph.node.model._graph_model._NodeGraphModel__common_node_props[qx_node.graph.node.model.type_][prev_name]

        if self.get_root_graph()._block_save:
            return

        if self.auto_update_prop:
            if self.is_root:
                graph = self
            else:
                graph = self.get_root_graph()
            
            graph.refresh_validation()
            graph.mx_parameter_changed.emit(qx_node, property_name, property_value)

    def on_port_disconnected(self, input_port=None, output_port=None):
        if not self.is_root:
            self.get_root_graph().on_port_disconnected(input_port, output_port)
            return

        if self.get_root_graph().auto_update_ng:
            self.update_mx_xml_data_from_graph()

    def on_mx_file_loaded(self, path):
        if self.get_root_graph().auto_update_ng:
            self.update_mx_xml_data_from_graph()

    def _on_property_bin_changed(self, node_id, prop_name, prop_value):
        """
        called when a property widget has changed in a properties bin.
        (emits the node object, property name, property value)

        Args:
            node_id (str): node id.
            prop_name (str): node property name.
            prop_value (object): python built in types.
        """
        node = self.get_node_by_id(node_id)

        # prevent signals from causing a infinite loop.
        if node.get_property(prop_name) != prop_value:
            node.set_property(prop_name, prop_value)

    def _deserialize_context_menu(self, menu, menu_data):
        if isinstance(menu_data, list):
            for obj in menu_data:
                if obj.get("type") == "menu":
                    for item in obj.get("items", []):
                        item["file"] = os.path.dirname(__file__) + "/hotkeys/hotkey_functions.py"

        super(QxNodeGraph, self)._deserialize_context_menu(menu, menu_data)

    def get_mx_node_def(self, type_name, def_name):
        if type_name not in self._node_factory._NodeFactory__nodes:
            return

        node_type = self._node_factory._NodeFactory__nodes[type_name]
        if not hasattr(node_type, "possible_mx_defs"):
            return

        possible_defs = node_type.possible_mx_defs
        if def_name:
            node_def = possible_defs[def_name]
        else:
            node_def = list(possible_defs.values())[0]

        return node_def

    def get_mx_doc_from_serialized_data(self, serialized_data, mx_parent=None, parent_id=None, parent_graph_data=None, qx_node_ids_to_mx_nodes=None):
        if not mx_parent:
            mx_parent = mx.createDocument()

        ng_abstraction = self.get_root_graph().widget.parent().act_ng_abstraction.isChecked()
        if parent_graph_data:
            ng_abstraction = False

        if ng_abstraction:
            for node_id in serialized_data.get("nodes", []):
                node_data = serialized_data["nodes"][node_id]
                if node_data["type_"] == "Other.QxGroupNode":
                    ng_abstraction = False

        if ng_abstraction:
            main_mx_node_graph = mx_parent.addNodeGraph("NG_main")

        qx_node_ids_to_mx_nodes = {} if qx_node_ids_to_mx_nodes is None else qx_node_ids_to_mx_nodes
        for node_id in serialized_data.get("nodes", []):
            node_data = serialized_data["nodes"][node_id]
            mx_def = self.get_mx_node_def(node_data["type_"], node_data.get("custom", {}).get("type"))
            if node_data["type_"] == "Other.QxGroupNode":
                mx_node = mx_parent.addNodeGraph(node_data["name"])
                self.get_mx_doc_from_serialized_data(node_data["subgraph_session"], mx_parent=mx_node, parent_id=node_id, parent_graph_data=serialized_data, qx_node_ids_to_mx_nodes=qx_node_ids_to_mx_nodes)
                output_node = None
                for subnode_id in node_data["subgraph_session"].get("nodes", []):
                    if node_data["subgraph_session"]["nodes"][subnode_id]["type_"] in ["Inputs.QxPortInputNode"]:
                        input_node = node_data["subgraph_session"]["nodes"][subnode_id]
                        input_node["id"] = subnode_id

                    if node_data["subgraph_session"]["nodes"][subnode_id]["type_"] in ["Outputs.QxPortOutputNode"]:
                        output_node = node_data["subgraph_session"]["nodes"][subnode_id]
                        output_node["id"] = subnode_id

                if output_node:
                    for port_data in output_node["input_ports"]:
                        for connection in node_data["subgraph_session"].get("connections", []):
                            if connection["in"][0] == output_node["id"] and connection["in"][1] == port_data["name"]:
                                connected_data = connection["out"]
                                connected_node_data = node_data["subgraph_session"]["nodes"][connected_data[0]]
                                connected_mx_def = self.get_mx_node_def(connected_node_data["type_"], connected_node_data.get("custom", {}).get("type"))
                                port_type = connected_mx_def.getActiveOutput(connected_data[1]).getType()
                                break
                        else:
                            continue

                        output = mx_node.addOutput(
                            port_data["name"], port_type
                        )
                        mx_sub_node = qx_node_ids_to_mx_nodes[connected_data[0]]
                        if mx_node.getType() == "multioutput":
                            con_output = mx_sub_node.getActiveOutput(connected_data[1])
                            output.setConnectedOutput(con_output)
                        else:
                            output.setConnectedNode(mx_sub_node)

            elif node_data["type_"] in ["Inputs.QxPortInputNode", "Outputs.QxPortOutputNode"]:
                continue
            elif mx_def.getNodeGroup() == "material":
                mx_node = mx_parent.addMaterialNode(node_data["name"])
            elif mx_def.getActiveOutputs():
                if ng_abstraction and mx_def.getActiveOutputs()[0].getType() != "surfaceshader":
                    mx_node = main_mx_node_graph.addNode(
                        mx_def.getNodeString(),
                        node_data["name"],
                        mx_def.getType(),
                    )
                else:
                    mx_node = mx_parent.addNode(
                        mx_def.getNodeString(),
                        node_data["name"],
                        mx_def.getType(),
                    )
            else:
                logger.warning("node has no outputs: %s" % mx_def.getNodeString())
                continue

            mx_node.setAttribute("xpos", str(node_data["pos"][0] * constants.NODEGRAPH_NODE_POSITION_SERIALIZATION_SCALE))
            mx_node.setAttribute("ypos", str(node_data["pos"][1] * constants.NODEGRAPH_NODE_POSITION_SERIALIZATION_SCALE))

            for input_data in node_data.get("input_ports", {}):
                val = node_data.get("custom", {}).get(input_data["name"], node_data.get("custom", {}).get(input_data["name"] + "0"))
                hasGeomProp = mx_def and bool(mx_def.getActiveInput(input_data["name"]).getDefaultGeomProp())  # the inputnodes and outputnodes of nodegraphs don't have a mx definition
                isConnected = None
                if hasGeomProp:
                    for connection in serialized_data.get("connections", []):
                        if connection["in"][0] == node_id and connection["in"][1] == input_data["name"]:
                            isConnected = True
                            break
                    else:
                        isConnected = False

                if node_data["type_"] == "Other.QxGroupNode":
                    for connection in node_data["subgraph_session"].get("connections", []):
                        if connection["out"][0] == input_node["id"] and connection["out"][1] == input_data["name"]:
                            connected_data = connection["in"]
                            connected_node_data = node_data["subgraph_session"]["nodes"][connected_data[0]]
                            connected_mx_def = self.get_mx_node_def(connected_node_data["type_"], connected_node_data.get("custom", {}).get("type"))
                            mx_input_type = connected_mx_def.getActiveInput(connected_data[1]).getType()
                            break
                    else:
                        continue
                else:
                    mx_input_type = mx_def.getActiveInput(input_data["name"]).getType()

                # temporary fix to avoid displacement validation warning
                if node_data["type_"] == "Material.Surfacematerial" and input_data["name"] == "displacementshader":
                    for connection in serialized_data.get("connections", []):
                        if connection["in"][0] == node_id and connection["in"][1] == "displacementshader":
                            break
                    else:
                        continue

                if node_data["type_"] == "Material.Surfacematerial" and input_data["name"] == "backsurfaceshader":
                    for connection in serialized_data.get("connections", []):
                        if connection["in"][0] == node_id and connection["in"][1] == "backsurfaceshader":
                            break
                    else:
                        continue

                if not hasGeomProp or isConnected:
                    mx_input = mx_node.addInput(input_data["name"], mx_input_type)
                    if not hasGeomProp:
                        self.set_mx_input_value(mx_input, val)

            for output_data in node_data.get("output_ports", {}):
                if node_data["type_"] == "Other.QxGroupNode":
                    continue
                
                mx_output_type = mx_def.getActiveOutput(output_data["name"]).getType()
                mx_node.addOutput(output_data["name"], mx_output_type)

            qx_node_ids_to_mx_nodes[node_id] = mx_node

        if ng_abstraction:
            main_mx_node_graph_outputs = {}
            for node_id in serialized_data.get("nodes", []):
                node_data = serialized_data["nodes"][node_id]
                if node_data["type_"] in ["Inputs.QxPortInputNode", "Outputs.QxPortOutputNode"]:
                    continue

                mx_def = self.get_mx_node_def(node_data["type_"], node_data.get("custom", {}).get("type"))
                for output_data in node_data.get("output_ports", {}):
                    mx_output_type = mx_def.getActiveOutput(output_data["name"]).getType()
                    if mx_output_type in ("material", "surfaceshader"):
                        continue

                    for connection in serialized_data.get("connections", []):
                        if connection["out"][0] != node_id:
                            continue

                        connected_node_data = serialized_data["nodes"][connection["in"][0]]
                        if connected_node_data["type_"] in ["Inputs.QxPortInputNode", "Outputs.QxPortOutputNode"]:
                            continue

                        connected_mx_def = self.get_mx_node_def(connected_node_data["type_"], connected_node_data.get("custom", {}).get("type"))
                        connected_port_type = connected_mx_def.getType()
                        if connected_port_type in ("material", "surfaceshader"):
                            output_name = f"output_{node_data['name']}_{output_data['name']}"
                            if main_mx_node_graph.getOutput(output_name):
                                continue

                            main_mx_node_graph_output = main_mx_node_graph.addOutput(
                                output_name,
                                mx_output_type,
                            )
                            mx_node = qx_node_ids_to_mx_nodes[node_id]
                            if mx_node.getType() == "multioutput":
                                connection_name = f"{output_data['name']}"
                                output = mx_node.getActiveOutput(connection_name)
                                main_mx_node_graph_output.setConnectedOutput(output)
                            else:
                                main_mx_node_graph_output.setConnectedNode(mx_node)

                            if node_id not in main_mx_node_graph_outputs:
                                main_mx_node_graph_outputs[node_id] = {}

                            main_mx_node_graph_outputs[node_id][
                                output_data["name"]
                            ] = main_mx_node_graph_output

        for connection in serialized_data.get("connections", []):
            if serialized_data["nodes"][connection["in"][0]]["type_"] in ["Outputs.QxPortOutputNode"]:
                continue

            mx_node = qx_node_ids_to_mx_nodes[connection["in"][0]]
            mx_input = mx_node.getActiveInput(connection["in"][1])
            if serialized_data["nodes"][connection["out"][0]]["type_"] in ["Inputs.QxPortInputNode"]:
                mx_input.setInterfaceName(connection["out"][1])
                mx_input.removeAttribute("value")
                continue
            
            connected_mx_node = qx_node_ids_to_mx_nodes[connection["out"][0]]
            if connected_mx_node.CATEGORY == "nodegraph":
                mx_input.setNodeGraphString(connected_mx_node.getName())
                mx_input.setConnectedOutput(
                    connected_mx_node.getActiveOutput(connection["out"][1])
                )
            elif ng_abstraction and connection["out"][0] in main_mx_node_graph_outputs:
                mx_input.setNodeGraphString(main_mx_node_graph.getName())
                mx_input.setConnectedOutput(
                    main_mx_node_graph_outputs[connection["out"][0]][connection["out"][1]]
                )
            else:
                mx_node = qx_node_ids_to_mx_nodes[connection["out"][0]]
                if mx_node.getType() == "multioutput":
                    output = mx_node.getActiveOutput(connection["out"][1])
                    mx_input.setConnectedOutput(output)
                else:
                    mx_input.setConnectedNode(mx_node)

        return mx_parent

    def set_mx_input_value(self, mx_input, val):
        # Convert vector like types
        mx_input_type = mx_input.getType()
        if mx_input_type == "vector2":
            val = mx.PyMaterialXCore.Vector2(val)
        elif mx_input_type == "vector3":
            val = mx.PyMaterialXCore.Vector3(val)
        elif mx_input_type == "color3":
            val = mx.PyMaterialXCore.Color3(val)
        elif mx_input_type == "color4":
            val = mx.PyMaterialXCore.Color4(val)

        # We do not need to set a value if it is connected to a node
        if val != "" or mx_input_type in ["string", "filename"]:
            if mx_input_type == "filename":
                mx_input.setValueString(val)
                mx_input.setAttribute("colorspace", "srgb_texture")
            else:
                mx_input.setValue(val, mx_input_type)

    def get_current_graph_data(self):
        serialized_data = self.serialize_session()
        for node_id in serialized_data.get("nodes", []):
            node_data = serialized_data["nodes"][node_id]
            if node_data["type_"] == "Other.QxGroupNode":
                node = self.get_node_by_id(node_id)
                if node.is_expanded:
                    node_data["subgraph_session"] = node.get_sub_graph().serialize_session()

        return serialized_data

    def get_current_mx_graph_doc(self):
        serialized_data = self.get_current_graph_data()
        doc = self.get_mx_doc_from_serialized_data(serialized_data)
        return doc

    def save_graph_as_mx_file(self, mx_file_path):
        mx_graph_doc = self.get_current_mx_graph_doc()
        mx.writeToXmlFile(mx_graph_doc, mx_file_path)
        logger.info(f"Wrote .mtlx file to {mx_file_path}")

    def get_mx_xml_data_from_graph(self):
        mx_graph_doc = self.get_current_mx_graph_doc()
        self.get_root_graph().widget.parent().validate(mx_graph_doc, popup=False)
        xml_data = mx.writeToXmlString(mx_graph_doc)
        return xml_data
    
    def refresh_validation(self):
        mx_graph_doc = self.get_current_mx_graph_doc()
        self.get_root_graph().widget.parent().validate(mx_graph_doc, popup=False)

    def update_mx_xml_data_from_graph(self):
        if self.get_root_graph()._block_save:
            return
        
        if not self.is_root:
            return self.get_root_graph().update_mx_xml_data_from_graph()

        xml_data = self.get_mx_xml_data_from_graph()
        if not xml_data:
            return

        # print(f"updated mx xml data: {xml_data}")
        logger.debug("updated mx xml data")
        self.mx_data_updated.emit(xml_data, True)

    def validate_mtlx_doc(self, doc=None):
        doc = doc or self.get_current_mx_graph_doc()
        doc = doc.copy()
        doc.importLibrary(self.mx_library_doc)
        result = doc.validate()
        return result

    def patch_relative_file_path_inputs(self, mx_node, base_dir):
        filename_inputs = [
            mx_input
            for mx_input in mx_node.getActiveInputs()
            if mx_input.getType() == "filename"
        ]
        for filename_input in filename_inputs:
            if mx.FilePath(filename_input.getValue()).isAbsolute():
                return

            filename_input.setValue(
                os.path.join(base_dir, filename_input.getValue()).replace(
                    "\\", "/"
                )
            )

    def load_graph_from_mx_file(self, mx_file_path):
        doc = mx.createDocument()
        # _libraryDir = os.path.join(os.path.join(self.core.extPath, "USD", "libraries"))
        # _searchPath = _libraryDir + mx.PATH_LIST_SEPARATOR + _exampleDir
        # _searchPath = _libraryDir

        # mx.readFromXmlFile(doc, path, _searchPath)
        new_defs = self.load_mx_libraries(library_path=mx_file_path, add_to_lib_doc=False)
        if new_defs:
            dirpath = os.path.dirname(mx_file_path)
            if dirpath not in os.getenv("PXR_MTLX_PLUGIN_SEARCH_PATHS", "").split(os.pathsep):
                os.environ["PXR_MTLX_PLUGIN_SEARCH_PATHS"] = os.getenv("PXR_MTLX_PLUGIN_SEARCH_PATHS", "") + os.pathsep + dirpath

        mx.readFromXmlFile(doc, mx_file_path)
        self.load_graph_from_mx_doc(doc)
        self.mx_file_loaded.emit(mx_file_path)

    def load_graph_from_mx_data(self, mx_data):
        doc = mx.createDocument()
        try:
            mx.readFromXmlString(doc, mx_data)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self.get_root_graph().widget.parent(), "Warning", 'Failed to load XML data:\n\n%s' % e)
            return

        self.load_graph_from_mx_doc(doc)
        self.mx_file_loaded.emit("")

    def load_graph_from_mx_doc(self, doc):
        with self.get_root_graph().block_save():
            self.clear_session()

            had_pos = False
            qx_node_to_mx_node = {}

            mx_nodes = doc.getNodes()
            mx_graphs = doc.getNodeGraphs()
            doc.importLibrary(self.mx_library_doc)

            # Create Nodes
            for cur_mx_node in mx_nodes:
                if cur_mx_node.hasAttribute("xpos") and cur_mx_node.hasAttribute("ypos"):
                    had_pos = True

                cur_qx_node = self.create_node_from_mx_node(cur_mx_node)

                qx_node_to_mx_node[cur_qx_node] = cur_mx_node

            for mx_graph in mx_graphs:
                ng_node = self.create_nodegraph_from_mx_nodegraph(mx_graph)
                for cur_mx_node in mx_graph.getNodes():
                    if cur_mx_node.hasAttribute("xpos") and cur_mx_node.hasAttribute("ypos"):
                        had_pos = True

                    cur_qx_node = self.create_node_from_mx_node(cur_mx_node, graph=ng_node.get_sub_graph())
                    # Change value type of node
                    qx_node_to_mx_node[cur_qx_node] = cur_mx_node

            for cur_qx_node, cur_mx_node in qx_node_to_mx_node.items():
                cur_qx_node.graph.connect_qx_inputs_from_mx_node(cur_qx_node, cur_mx_node)

            graphs = [self.get_root_graph()]
            graphs += list(self.sub_graphs.values())
            for graph in graphs:
                if not had_pos:
                    graph.auto_layout_nodes()

                if not graph.is_root:
                    graph.parent_graph.collapse_group_node(graph.node)

    def load_image_file(self, filepath, xoffset=0, yoffset=0):
        local_pos = self.viewer().mapFromGlobal(QtGui.QCursor.pos())
        pos = self.viewer().mapToScene(local_pos)
        name = os.path.splitext(os.path.basename(filepath))[0]
        qx_node = self.create_node(
            "Texture2d.Image",
            name=name,
            selected=True,
            pos=[pos.x() + xoffset, pos.y() + yoffset],
        )
        qx_node.set_property("type", "color3")
        qx_node.set_property("file", filepath)
        return qx_node

    # TODO: move to qx_node
    def connect_qx_inputs_from_mx_node(self, qx_node, mx_node):
        for mx_input in mx_node.getActiveInputs():
            mx_connected_port = mx_input.getConnectedOutput()
            # Not every input has a connections
            if mx_connected_port:
                ng_name = mx_connected_port.getParent().getName()
                mx_input_name = mx_input.getName()
                qx_input_port = qx_node.get_input(mx_input_name)
                qx_input_node = self.get_node_by_name(ng_name)
                qx_output_port = qx_input_node.get_output(mx_connected_port.getName())
                qx_input_port.connect_to(qx_output_port)

            mx_connected_node = mx_input.getConnectedNode()
            if mx_connected_node:
                if mx_connected_port and mx_connected_port.getParent().CATEGORY == "nodegraph":
                    port_node = qx_input_node.get_sub_graph().get_output_port_nodes()[0]
                    qx_input_port = port_node.get_input(mx_connected_port.getName())
                    mx_input_node_name = mx_connected_node.getName()
                    qx_input_node = qx_input_node.get_sub_graph().get_node_by_name(mx_input_node_name)
                    mx_output_name = "out"
                    qx_output_port = qx_input_node.get_output(mx_output_name)
                else:
                    mx_input_name = mx_input.getName()
                    mx_output_name = "out"

                    mx_input_node_name = mx_connected_node.getName()

                    qx_input_node = self.get_node_by_name(mx_input_node_name)
                    qx_input_port = qx_node.get_input(mx_input_name)
                    qx_output_port = qx_input_node.get_output(mx_output_name)

                if qx_input_port:
                    qx_input_port.connect_to(qx_output_port)
                else:
                    logger.warning("invalid in port: {mx_input_name}")

            if mx_input.hasInterfaceName():
                intf_name = mx_input.getInterfaceName()
                port_node = qx_node.graph.get_input_port_nodes()[0]
                out_port = port_node.get_output(intf_name)
                qx_input_port = qx_node.get_input(mx_input.getName())
                out_port.connect_to(qx_input_port)

    def connect_qx_ng_ports_from_mx_ng(self, ng_node, mx_ng, mx_def):
        out_port_node = ng_node.get_sub_graph().get_output_port_nodes()[0]
        for in_port in out_port_node.input_ports():
            mx_ng_output = mx_ng.getActiveOutput(in_port.name())
            if not mx_ng_output:
                continue

            mx_connected_node = mx_ng_output.getConnectedNode()
            mx_input_node_name = mx_connected_node.getName()
            qx_input_node = ng_node.get_sub_graph().get_node_by_name(mx_input_node_name)
            qx_output_port = qx_input_node.get_output("out")
            in_port.connect_to(qx_output_port)

        in_port_node = ng_node.get_sub_graph().get_input_port_nodes()[0]
        for mx_node in mx_ng.getNodes():
            for mx_input in mx_node.getActiveInputs():
                if mx_input.hasInterfaceName():
                    intf_name = mx_input.getInterfaceName()
                    out_port = in_port_node.get_output(intf_name)
                    qx_output_node = ng_node.get_sub_graph().get_node_by_name(mx_node.getName())
                    qx_input_port = qx_output_node.get_input(mx_input.getName())
                    out_port.connect_to(qx_input_port)

    def create_node_from_mx_node(
        self,
        mx_node,
        name=None,
        selected=True,
        color=None,
        text_color=None,
        pos=None,
        push_undo=True,
        graph=None
    ):
        graph = graph or self
        qx_node_type = self.get_qx_node_type_from_mx_node(mx_node)
        if not pos and mx_node.hasAttribute("xpos") and mx_node.hasAttribute("ypos"):
            pos = [
                float(mx_node.getAttribute("xpos")) / constants.NODEGRAPH_NODE_POSITION_SERIALIZATION_SCALE,
                float(mx_node.getAttribute("ypos")) / constants.NODEGRAPH_NODE_POSITION_SERIALIZATION_SCALE
                ]

        name = name or mx_node.getName()
        qx_node = graph.create_node(
            qx_node_type,
            name=name,
            selected=selected,
            color=color,
            text_color=text_color,
            pos=pos,
            push_undo=push_undo
        )
        qx_node.update_from_mx_node(mx_node)
        return qx_node

    def create_nodegraph_from_mx_nodegraph(
        self,
        mx_node,
        name=None,
        selected=True,
        color=None,
        text_color=None,
        pos=None,
        push_undo=True,
        create_ports=True
    ):
        name = name or mx_node.getName()
        if not pos and mx_node.hasAttribute("xpos") and mx_node.hasAttribute("ypos"):
            pos = [
                float(mx_node.getAttribute("xpos")) / constants.NODEGRAPH_NODE_POSITION_SERIALIZATION_SCALE,
                float(mx_node.getAttribute("ypos")) / constants.NODEGRAPH_NODE_POSITION_SERIALIZATION_SCALE
                ]

        qx_node = self.create_node(
            "Other.QxGroupNode",
            name=name,
            selected=selected,
            color=color,
            text_color=text_color,
            pos=pos,
            push_undo=push_undo
        )
        qx_node.create_property("nodedef", mx_node.getNodeDef())
        if create_ports:
            for output in mx_node.getOutputs():
                color = qx_node_module.QxNodeBase._random_color_from_string(str(output.getType()))
                qx_node.add_output(output.getName(), color=color)

            for minput in mx_node.getInputs():
                qx_node_module.QxNode.create_property_from_mx_input(minput, qx_node)
                color = qx_node_module.QxNodeBase._random_color_from_string(str(minput.getType()))
                in_port = qx_node.add_input(minput.getName(), color=color)
                in_port.view.setToolTip(minput.getType())
            
        self.expand_group_node(qx_node)
        return qx_node

    def get_qx_node_type_from_mx_node(self, mx_node):
        mx_node_type = mx_node.getType()
        # There are some nodes duplicate in multiple categories with different behaviour
        # Example: pbr.multiply & math.multiply
        possible_qx_nodes = self.node_factory.names[
            mx_node.getCategory().capitalize()
        ]

        # If the node appears under multiple categories, choose the category that contains the
        # node definition with the corresponding type of mx_node_type
        if len(possible_qx_nodes) > 1:
            qx_node_type_to_create = None
            for possible_qx_node_type in possible_qx_nodes:
                current_possible_mx_defs = self.node_factory.nodes[
                    possible_qx_node_type
                ].possible_mx_defs
                for mx_def_type in current_possible_mx_defs:
                    current_possible_mx_def = current_possible_mx_defs[mx_def_type]
                    is_match = True
                    for mx_input in mx_node.getActiveInputs():
                        cur_mx_input = current_possible_mx_def.getActiveInput(mx_input.getName())
                        if mx_input.getType() != cur_mx_input.getType():
                            is_match = False

                    for mx_output in mx_node.getActiveOutputs():
                        cur_mx_output = current_possible_mx_def.getActiveOutput(mx_output.getName())
                        if mx_output.getType() != cur_mx_output.getType():
                            is_match = False

                    if mx_node_type != current_possible_mx_def.getActiveOutputs()[0].getType():
                        is_match = False

                    if is_match:
                        qx_node_type_to_create = possible_qx_node_type

                # if mx_node_type in current_possible_mx_defs:
                #     qx_node_type_to_create = possible_qx_node_type
                #     break

        else:
            qx_node_type_to_create = possible_qx_nodes[0]
        return qx_node_type_to_create

    def delete_nodes(self, nodes, push_undo=True):
        self.has_deleted_nodes = False
        with self.get_root_graph().block_save():
            super(QxNodeGraph, self).delete_nodes(nodes, push_undo)

        if self.has_deleted_nodes and self.get_root_graph().auto_update_ng:
            self.update_mx_xml_data_from_graph()

    def get_unique_name(self, name):
        """
        Creates a unique node name to avoid having nodes with the same name.

        Args:
            name (str): node name.

        Returns:
            str: unique node name.
        """
        name = "_".join(name.split())
        node_names = [n.name() for n in self.all_nodes()]
        if name not in node_names:
            return name

        regex = re.compile(r"[\w ]+(?: )*(\d+)")
        search = regex.search(name)
        if not search:
            for x in range(1, len(node_names) + 2):
                new_name = "{}_{}".format(name, x)
                if new_name not in node_names:
                    return new_name

        version = search.group(1)
        name = name[: len(version) * -1].strip()
        for x in range(1, len(node_names) + 2):
            new_name = "{}_{}".format(name, x)
            if new_name not in node_names:
                return new_name

    def expand_group_node(self, node):
        """
        Expands a group node session in a new tab.

        Args:
            node (NodeGraphQt.GroupNode): group node.

        Returns:
            SubGraph: sub node graph used to manage the group node session.
        """
        if not isinstance(node, GroupNode):
            return
        if self._widget is None:
            raise RuntimeError('NodeGraph.widget not initialized!')

        self.viewer().clear_key_state()
        self.viewer().clearFocus()

        if node.id in self._sub_graphs:
            sub_graph = self._sub_graphs[node.id]
            tab_index = self._widget.indexOf(sub_graph.widget)
            self._widget.setCurrentIndex(tab_index)
            return sub_graph

        # build new sub graph.
        node_factory = copy.deepcopy(self.node_factory)
        layout_direction = self.layout_direction()
        # custom start  - replace Subgraph with own and emit node graph changed signal
        # sub_graph = SubGraph(self,
        #                      node=node,
        #                      node_factory=node_factory,
        #                      layout_direction=layout_direction)
        
        sub_graph = self.subnodegraph_class(self, node=node, node_factory=node_factory, layout_direction=layout_direction)
        # if not self.get_root_graph()._block_save:
        #     self.node_graph_changed.emit(sub_graph)
        # custom end

        # populate the sub graph.
        session = node.get_sub_graph_session()
        sub_graph.deserialize_session(session)

        # store reference to expanded.
        self._sub_graphs[node.id] = sub_graph

        # open new tab at root level.
        self.widget.add_viewer(sub_graph.widget, node.name(), node.id)

        # custom start  - avoid scrollbar
        sub_graph.widget.navigator.setMaximumHeight(45)
        # custom end
        return sub_graph

    def get_node_by_id(self, node_id=None):
        """
        Returns the node from the node id string.

        Args:
            node_id (str): node id (:attr:`NodeObject.id`)

        Returns:
            NodeGraphQt.NodeObject: node object.
        """
        # custom start - lookup by self.current_node_graph instead of just self
        # return self._model.nodes.get(node_id, None)
        node = self._model.nodes.get(node_id, None)
        if node:
            return node

        graphs = [self.get_root_graph()]
        graphs += list(self.sub_graphs.values())
        for graph in graphs:
            node = graph._model.nodes.get(node_id, None)
            if node:
                return node

    def _on_connection_sliced(self, ports):
        with self.get_root_graph().block_save():
            super(QxNodeGraph, self)._on_connection_sliced(ports)

        self.on_port_disconnected()

    def toggle_node_search(self):
        self.viewer()._search_widget.port_to_connect = None
        super().toggle_node_search()
