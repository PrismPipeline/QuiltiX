import random
import logging

from qtpy import QtCore, QtGui  # type: ignore

import MaterialX as mx  # type: ignore
from NodeGraphQt import BaseNode, GroupNode
from NodeGraphQt.qgraphics.node_base import NodeItem
from NodeGraphQt.qgraphics.node_group import GroupNodeItem
from NodeGraphQt.constants import (
    NodePropWidgetEnum,
    PortTypeEnum,
)
from NodeGraphQt.nodes.port_node import PortInputNode, PortOutputNode

from QuiltiX import mx_node
from QuiltiX import qx_port


logger = logging.getLogger(__name__)

# The node graph stores the types of each property, meaning the type of a property cannot change.
# When a node changes its type (fe. from color3 to vector3) sometimes one or multiple properties of
# the node also need to change their type, which is currently not possible.
# Therefore some properties need to have their name prefixed by the node type.
# This list stores these properties.
MULTI_TYPE_PROPERTY_NAMES = [
    "default2",
]


class QxNodeBase(BaseNode):
    def __init__(self, qgraphics_item=None, node_graph=None):
        """The main purpose of this class is to overwrite the NodeItem with a add_in/output functions
        that call our own PortItems with custom drawing, instead of NodeGraphQts

        It also holds functions common to both QxNode & QxGroupNode
        """
        super(QxNodeBase, self).__init__(qgraphics_item or QxNodeItem)

        # View node is the display part of the node. There currently is no
        # connection between them, so we add it on init.
        self._extend_view_node()

        # Initialize graph attributes here, so they can be accessed during init
        if node_graph is not None:
            self._graph = node_graph
            self.model._graph_model = node_graph.model

    def _extend_view_node(self):
        self._view.basenode = self

    @staticmethod
    def _random_color_from_string(string_seed):
        # Generate random color based on input type
        color = []
        for i in range(3):
            random.seed(string_seed + f"{i}")
            color.append(random.randrange(255))

        return tuple(color)

    def refresh_port_tooltips(self):
        for node_input in self.input_ports():
            node_input.view.refresh_tool_tip()

        for node_output in self.output_ports():
            node_output.view.refresh_tool_tip()

    def refresh_port_colors(self):
        for node_input in self.input_ports():
            mx_input = self.current_mx_def.getActiveInput(node_input.name())
            node_input.color = self._random_color_from_string(str(mx_input.getType()))

        for node_output in self.output_ports():
            mx_output = self.current_mx_def.getActiveOutput(node_output.name())
            node_output.color = self._random_color_from_string(str(mx_output.getType()))


class QxNode(QxNodeBase):
    possible_mx_defs = None

    def __init__(self, node_type=None, node_graph=None):
        super(QxNode, self).__init__(node_graph)

        # Remove current node data
        self.set_port_deletion_allowed(True)
        self.set_ports({"input_ports": [], "output_ports": []})
        # TODO maybe more selective?
        self.model._custom_prop = {}

        if node_type is None:
            self.current_mx_def = next(iter(self.possible_mx_defs.values()))
            self.add_type_property()
        else:
            self.current_mx_def = self.possible_mx_defs[node_type]
            self.add_type_property(current_type_name=node_type)

        self.initialize_type()
        logger.debug(f"Initialized {self.NODE_NAME} of type {self.type_}")

    @classmethod
    def from_mx_node(cls, mx_node, node_graph=None):
        mx_def_type = cls.get_displaytype_from_mx_node(cls, mx_node)
        qx_node = cls(node_type=mx_def_type, node_graph=node_graph)
        return qx_node

    def get_displaytype_from_mx_node(self, mx_node):
        from QuiltiX.mx_node import get_displaytype_from_mx_def
        mx_def = mx_node.getNodeDef()
        if mx_def:
            return get_displaytype_from_mx_def(mx_def)

        mx_category = mx_node.getCategory()
        if mx_category in self.possible_mx_defs:
            return mx_category

        logger.warning(
            f"Could not find matching definition for type '{mx_node.getType()}' of node '{mx_node.getName()}'."
        )

    def update_from_mx_node(self, mx_node):
        mx_def_type = self.get_displaytype_from_mx_node(mx_node)
        if not mx_def_type:
            return

        self.change_type(mx_def_type)
        self.complete_outputs_for_multioutputs(mx_node)
        self.set_properties_from_mx_node(mx_node)

    def add_type_property(self, current_type_name=None):
        """Add a type property for nodes that have more than one MaterialX Definition."""
        if len(self.possible_mx_defs) > 1:
            mx_def_names = self.possible_mx_defs.keys()

            if not current_type_name:
                current_type_name = next(iter(mx_def_names))

            self.create_property(
                name="type",
                value=current_type_name,
                items=mx_def_names,
                widget_type=NodePropWidgetEnum.QCOMBO_BOX.value,
            )

    def get_widget_type(self, name):
        mx_input = self.current_mx_def.getActiveInput(name)
        if not mx_input:
            return self.model.get_widget_type(name)

        wtype = self.get_widget_type_from_mx_type(mx_input.getType())
        return wtype

    def set_ports(self, port_data):
        super().set_ports(port_data)
        self.refresh_port_colors()
        self.refresh_port_tooltips()

    @classmethod
    def get_widget_type_from_mx_type(cls, mx_type):
        if mx_type == "float":
            widget_type = NodePropWidgetEnum.DOUBLE_SLIDER.value
        elif mx_type == "integer":
            widget_type = NodePropWidgetEnum.SLIDER.value
        elif mx_type == "vector2":
            widget_type = NodePropWidgetEnum.VECTOR2.value
        elif mx_type == "vector3":
            widget_type = NodePropWidgetEnum.VECTOR3.value
        elif mx_type == "vector4":
            widget_type = NodePropWidgetEnum.VECTOR4.value
        elif mx_type == "color3":
            widget_type = NodePropWidgetEnum.COLOR_PICKER.value
        elif mx_type == "color4":
            widget_type = NodePropWidgetEnum.COLOR4_PICKER.value
        elif mx_type == "filename":
            widget_type = NodePropWidgetEnum.FILE_OPEN.value
        elif mx_type in ["string", "geomname"]:
            widget_type = NodePropWidgetEnum.QLINE_EDIT.value
        elif mx_type == "boolean":
            widget_type = NodePropWidgetEnum.QCHECK_BOX.value
        elif mx_type in [
            "surfaceshader",
            "displacementshader",
            "volumeshader",
            "lightshader",
            "BSDF",
            "EDF",
            "VDF",
        ]:
            widget_type = NodePropWidgetEnum.QLABEL.value
        elif mx_type in [
            "matrix33",
            "matrix44",
            "integerarray",
            "floatarray",
            "color3array",
            "color4array",
            "vector2array",
            "vector3array",
            "vector4array",
            "stringarray",
            "geomnamearray"
        ]:
            widget_type = NodePropWidgetEnum.QLINE_EDIT.value
        else:
            logger.warning(f"Unknown prop type for MaterialX input of type: {mx_type}")
            widget_type = NodePropWidgetEnum.QLINE_EDIT.value

        return widget_type

    def initialize_type(self):
        # TODO: overhaul type conversion
        for mx_input in self.current_mx_def.getActiveInputs():
            color = self._random_color_from_string(mx_input.getType())
            self.add_input(mx_input.getName(), color=color)
            self.__class__.create_property_from_mx_input(mx_input, self)

        for mx_output in self.current_mx_def.getActiveOutputs():
            # TODO: actively chose colors instead of random
            color = self._random_color_from_string(str(mx_output.getType()))
            mx_output_name = mx_output.getName()
            self.add_output(mx_output_name, color=color)

        self.refresh_port_tooltips()

    @classmethod
    def create_property_from_mx_input(cls, mx_input, node):
        mx_input_value = mx_input.getValue()
        mx_input_name = mx_input.getName()
        mx_input_type = mx_input.getType()
        value_range = None

        if mx_input_type in ["float", "integer"]:
            ui_min_value = mx_input.getAttribute(mx_input.UI_MIN_ATTRIBUTE)
            ui_max_value = mx_input.getAttribute(mx_input.UI_MAX_ATTRIBUTE)
            if ui_min_value and ui_max_value:
                value_range = [ui_min_value, ui_max_value]

        if mx_input_value and "color" in mx_input_type:
            color_type_map = {
                "color3": mx.PyMaterialXCore.Vector3,
                "color4": mx.PyMaterialXCore.Vector4
            }
            mx_input_value = list(color_type_map[mx_input_type](mx_input_value))
        elif mx_input_value and "vector" in mx_input_type.lower():
            mx_input_value = [i for i in mx_input_value]

        # TODO: actively chose colors instead of random
        widget_type = cls.get_widget_type_from_mx_type(mx_input_type)
        if mx_input_type == "float":
            if mx_input_value is None:
                mx_input_value = 0
            if value_range:
                value_range = [float(i) for i in value_range]
        elif mx_input_type == "integer":
            if mx_input_value is None:
                mx_input_value = 0
            if value_range:
                value_range = [int(i) for i in value_range]
        elif mx_input_type == "vector2":
            if mx_input_value is None:
                mx_input_value = [0, 0]
        elif mx_input_type == "vector3":
            if mx_input_value is None:
                mx_input_value = [0, 0, 0]
        elif mx_input_type == "vector4":
            if mx_input_value is None:
                mx_input_value = [0, 0, 0, 0]
        elif mx_input_type == "color3":
            if mx_input_value is None:
                mx_input_value = [0, 0, 0]
        elif mx_input_type == "color4":
            if mx_input_value is None:
                mx_input_value = [0, 0, 0, 1]
        elif mx_input_type == "filename":
            if mx_input_value is None:
                mx_input_value = ""
        elif mx_input_type in ["string", "geomname"]:
            if mx_input_value is None:
                mx_input_value = ""

        property_name = cls.get_property_name_from_mx_input(node, mx_input_name)
        node.create_property(
            property_name, mx_input_value, widget_type=widget_type, range=value_range
        )

    def get_mx_def_name_from_data_type(self, data_type, from_port="in"):
        if from_port not in ["in", "out"]:
            raise ValueError(f"Invalid port type: {from_port}")

        if data_type in self.possible_mx_defs:
            return data_type

        # Check additionally for matching types in the first output
        if from_port == "in":
            mx_def_type_name_to_port_data_type_map = {
                mx_def_name: mx_def.getInputs()[0].getType()
                for mx_def_name, mx_def in self.possible_mx_defs.items()
                if mx_def.getInputs()
            }
        elif from_port == "out":
            mx_def_type_name_to_port_data_type_map = {
                mx_def_name: mx_def.getOutputs()[0].getType()
                for mx_def_name, mx_def in self.possible_mx_defs.items()
                if mx_def.getOutputs()
            }

        if data_type not in mx_def_type_name_to_port_data_type_map.values():
            logger.warn(f"Could not find definition of type {data_type} for node {self.name()}")
            return
        else:
            # There can be multiple mx defs that match. Make a "good" guess with the first one we find :)
            possible_type_names = [
                mx_def_name
                for mx_def_name, mx_def_type_name in mx_def_type_name_to_port_data_type_map.items()
                if mx_def_type_name == data_type
            ]
            data_type = possible_type_names[0]
            return data_type

    def change_type(self, type_name):
        if type_name not in self.possible_mx_defs:
            logger.warn(f"Could not find definition of type {type_name} for node {self.name()}")
            return

        # Store connections & values for them to be restored later
        original_values = self.properties()["custom"]
        original_mx_def = self.current_mx_def
        original_input_connections = {inp: input_port.connected_ports() for inp, input_port in self.inputs().items()}
        original_output_connections = {
            outp: output_port.connected_ports() for outp, output_port in self.outputs().items()
        }

        for p in self.input_ports():
            p.clear_connections()
        for p in self.output_ports():
            p.clear_connections()

        self.current_mx_def = self.possible_mx_defs[type_name]

        # Remove current node data
        self.set_port_deletion_allowed(True)
        self.set_ports({"input_ports": [], "output_ports": []})
        # TODO maybe more selective?
        self.model._custom_prop = {}

        # Readd current node data
        self.add_type_property(current_type_name=type_name)
        self.initialize_type()

        self.refresh_port_tooltips()

        self._restore_values(original_values, original_mx_def)

        # TODO: create convert node between connections if port types don't match and if conversion possible
        self._restore_input_connections(original_input_connections)
        self._restore_output_connections(original_output_connections)

    def _restore_values(self, original_values, original_mx_def):
        original_types = { i.getName(): i.getType() for i in original_mx_def.getInputs() }
        new_types = { i.getName(): i.getType() for i in self.current_mx_def.getInputs() }

        for property_name, value in original_values.items():
            # Skip if the property name describes the node type
            if property_name == "type":
                continue

            # Skip if the property doesn't exist on the node's custom properties anymore
            if property_name not in self.properties()["custom"]:
                continue

            # Skip if the property name has not changed, but the property type has
            if (
                property_name in original_types
                and property_name in new_types
                and original_types[property_name] != new_types[property_name]
            ):
                continue

            self.set_property(property_name, value)

    def _restore_input_connections(self, original_input_connections):
        for input_name, input_port in self.inputs().items():
            if input_name in original_input_connections:
                input_port_type = input_port.view.get_mx_port_type()

                # inputs can only have one connection
                original_connected_port = next(iter(original_input_connections[input_name]), None)  
                if original_connected_port:
                    original_connected_port_type = original_connected_port.view.get_mx_port_type()

                    if original_connected_port_type == input_port_type:
                        logger.debug(f"Reconnecting port {input_name} with {original_connected_port.name()}")
                        input_port.connect_to(original_connected_port)

    def _restore_output_connections(self, original_output_connections):
        for output_name, output_port in self.outputs().items():
            if output_name in original_output_connections:
                output_port_type = output_port.view.get_mx_port_type()

                original_connected_ports = original_output_connections[output_name]
                # outputs can have multiple connections
                for original_connected_port in original_connected_ports:
                    if not original_connected_port.node():
                        continue
                    elif original_connected_port.node().type_ in ["Inputs.QxPortInputNode", "Outputs.QxPortOutputNode"]:
                        pass
                    else:
                        original_connected_port_type = original_connected_port.view.get_mx_port_type()

                    if original_connected_port_type == output_port_type:
                        logger.debug(f"Reconnecting port {output_name} with {original_connected_port.name()}")
                        output_port.connect_to(original_connected_port)

    def create_property(
        self,
        name,
        value,
        items=None,
        range=None,
        widget_type=NodePropWidgetEnum.HIDDEN.value,
        tab=None,
    ):
        # name = self.get_mx_input_name_from_property_name(name)
        super().create_property(name, value, items, range, widget_type, tab)

    def complete_outputs_for_multioutputs(self, mx_node):

        # Handle with node outputs are not explicitly specified on
        # a multioutput node. Note that this must be done
        # before the qx_node is created and before connections are made.
        if mx_node.getType() != "multioutput":
            return
        
        mx_node_def = mx_node.getNodeDef()
        if not mx_node_def:
            return
        
        for mx_output in mx_node_def.getActiveOutputs():
            mx_output_name = mx_output.getName()
            if not mx_node.getOutput(mx_output_name):
                mx_output_type = mx_output.getType()
                mx_node.addOutput(mx_output_name, mx_output_type)

    def set_properties_from_mx_node(self, mx_node):

        for mx_input in mx_node.getActiveInputs():
            mx_input_value = mx_input.getValue()
            mx_input_name = mx_input.getName()
            mx_input_type = mx_input.getType()

            # TODO: split into function
            if mx_input_value:
                if mx_input_type in ["color3", "color4"]:
                    mx_input_value = tuple(mx_input_value)
                elif mx_input_type in ["vector2", "vector3", "vector4"]:
                    if type(mx_input_value) == str:
                        mx_input_value = [v.strip() for v in mx_input_value.split(",")]

                    mx_input_value = tuple(mx_input_value)
                elif mx_input_type == "filename":
                    mx_input_value = mx_input.getResolvedValueString()

                property_name = self.get_property_name_from_mx_input(
                    mx_input_name
                )
                self.set_property(property_name, mx_input_value)

    def get_property_name_from_mx_input(self, mx_input_name):
        # FIXME: property name can't be one of the defaults. currently ugly hacked
        # defaults : ['type_', 'id', 'icon', 'name', 'color',
        # 'border_color', 'text_color', 'disabled', 'selected', 'visible',
        # 'width', 'height', 'pos', 'inputs', 'outputs',
        # 'port_deletion_allowed', 'subgraph_session']
        if mx_input_name in MULTI_TYPE_PROPERTY_NAMES:
            prefix = next(
                (
                    mx_def_type
                    for mx_def_type, mx_def in self.possible_mx_defs.items()
                    if mx_def == self.current_mx_def
                ),
                None,
            )
            property_name = ".".join((prefix, mx_input_name))
        elif mx_input_name in self.model.properties.keys():
            property_name = mx_input_name + "0"
        else:
            property_name = mx_input_name
        return property_name

    def get_mx_input_name_from_property_name(self, property_name):
        return property_name
        # prefix = next(
        #     (
        #         mx_def_type
        #         for mx_def_type, mx_def in self.possible_mx_defs.items()
        #         if mx_def == self.current_mx_def
        #     ),
        #     "",
        # )
        # adjusted_multi_type_property_names = [
        #     ".".join((prefix, p_name)) for p_name in MULTI_TYPE_PROPERTY_NAMES
        # ]
        # if property_name in adjusted_multi_type_property_names:
        #     mx_input_name = property_name.replace(f"{prefix}.", "")
        # Removing this fixes nodes with a "color" input
        # Why was this here again?
        # elif property_name in self.model.properties.keys():
        #     mx_input_name = property_name[:-1]
        # else:
        #     mx_input_name = property_name

        # return mx_input_name


class QxGroupNodeBase(GroupNode):
    def __init__(self, qgraphics_item=None):
        """Soul purpose is to overwrite the NodeItem with a add_in/output functions
        that call our own PortItems with custom drawing, instead of NodeGraphQts
        """
        super(QxGroupNodeBase, self).__init__(qgraphics_item or QxGroupNodeItem)


class QxGroupNode(QxGroupNodeBase):
    # TODO: implement input/output drawing
    __identifier__ = 'Other'
    __label__ = 'Other.Nodegraph'

    # set the initial default node name.
    NODE_NAME = 'Nodegraph'

    def __init__(self, qgraphics_item=None):
        super(QxGroupNode, self).__init__(qgraphics_item or QxGroupNodeItem)
        self.set_color(50, 8, 25)
        self.possible_mx_defs = {}
        self.set_port_deletion_allowed(True)

    def expand(self):
        sub_graph = super(QxGroupNode, self).expand()
        self.get_sub_graph().get_output_port_nodes()[0].refresh_port_colors()
        self.get_sub_graph().get_input_port_nodes()[0].refresh_port_colors()
        return sub_graph

    def get_widget_type(self, name):
        return self.model.get_widget_type(name)

    def add_output(self, name='output', multi_output=True, display_name=True,
                   color=None, locked=False, painter_func=None):
        port = super(GroupNode, self).add_output(
            name=name,
            multi_output=multi_output,
            display_name=display_name,
            color=color,
            locked=locked,
            painter_func=painter_func
        )
        if self.is_expanded:
            output_port = self.get_sub_graph().get_output_port_nodes()[0]
            if not output_port.get_input(port.name()):
                output_port.add_input(port.name())

        return port

    def add_input(self, name='input', multi_input=True, display_name=True,
                  color=None, locked=False, painter_func=None):
        port = super(GroupNode, self).add_input(
            name=name,
            multi_input=multi_input,
            display_name=display_name,
            color=color,
            locked=locked,
            painter_func=painter_func
        )
        if self.is_expanded:
            input_port = self.get_sub_graph().get_input_port_nodes()[0]
            if not input_port.get_output(port.name()):
                input_port.add_output(port.name())

        return port


class QxPortInputNode(PortInputNode):

    __identifier__ = 'Inputs'

    def __init__(self, qgraphics_item=None, parent_port=None):
        super(QxPortInputNode, self).__init__(
            qgraphics_item or QxNodeItem, parent_port
        )
        self.set_port_deletion_allowed(True)
        inpt = self.add_output("Next Input")
        inpt.view.setToolTip("Next Input")

    def get_widget_type(self, name):
        return self.model.get_widget_type(name)

    def add_output(self, name='output', multi_output=True, display_name=True,
                   color=None, locked=False, painter_func=None):
        outpt = super(PortInputNode, self).add_output(
            name=name,
            multi_output=multi_output,
            display_name=True,
            color=color,
            locked=locked,
            painter_func=None
        )
        if name != "Next Input":
            self.create_property(
                name=f"Input #{len(self.output_ports())-1}",
                value=name,
                widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            )
            if len(self._outputs) > 1:
                self.view._output_items.move_to_end(list(self.view._output_items.keys())[-2])
                self._outputs.append(self._outputs.pop(len(self._outputs)-2))
                self.update()
                self.view.draw_node()

        return outpt

    def on_output_connected(self, in_port, out_port):
        if in_port.name() == "Next Input":
            name = "in_" + out_port.node().name()
            while self.get_output(name):
                if "_" in name:
                    base, suffix = name.rsplit("_", 1)
                    try:
                        curnum = int(suffix)
                    except:
                        curnum = 0
                        base = name

                    name = base + "_" + str(curnum + 1)
                else:
                    name += "_1"

            in_port.color = QxNodeBase._random_color_from_string(out_port.view.get_mx_port_type())
            in_port.model.name = name
            in_port.view.name = name
            text_item = self.view.get_output_text_item(in_port.view)
            text_item.setPlainText(name)
            out_port.model.connected_ports[self.id] = [name]
            self.model.outputs[name] = in_port.model
            self.create_property(
                name=f"Input #{len(self.output_ports())}",
                value=name,
                widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            )
            outpt = self.add_output("Next Input")
            outpt.view.setToolTip("Next Input")

            props = out_port.node().model._graph_model.get_node_common_properties(out_port.node().type_)
            widget_type = props[out_port.name()]["widget_type"]
            self.graph.node.create_property(
                name=name,
                value=out_port.node().get_property(out_port.name()),
                widget_type=widget_type,
            )
            ng_port = self.graph.node.add_input(name, color=in_port.color)
            in_port.view.setToolTip(out_port.view.get_mx_port_type())
            ng_port.view.setToolTip(out_port.view.get_mx_port_type())

    def on_output_disconnected(self, in_port, out_port):
        if not getattr(self.graph, "is_collapsing", False) and not in_port.connected_ports():
            self.graph.node.get_input(in_port.name()).clear_connections()
            self.graph.node.delete_input(in_port.name())
            del self.properties()["custom"][f"Input #{self.output_ports().index(in_port) + 1}"]
            del self.graph.node.model._custom_prop[in_port.name()]
            del self.graph.node.model._graph_model._NodeGraphModel__common_node_props[self.graph.node.model.type_][in_port.name()]
            self.delete_output(in_port)
            self.refresh_input_props()

    def refresh_input_props(self):
        todel = [prop for prop in self.model._custom_prop if prop.startswith("Input #")]
        for prop in todel:
            if prop.startswith("Input #"):
                del self.model._custom_prop[prop]

        for idx, port in enumerate(self.output_ports()):
            if port.name() == "Next Input":
                continue

            self.create_property(
                name=f"Input #{idx+1}",
                value=port.name(),
                widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            )

    def refresh_port_colors(self):
        for port in self.output_ports():
            cports = port.connected_ports()
            if not cports:
                continue

            port.color = QxNodeBase._random_color_from_string(cports[0].view.get_mx_port_type())


class QxPortOutputNode(PortOutputNode):

    __identifier__ = 'Outputs'

    def __init__(self, qgraphics_item=None, parent_port=None):
        super(QxPortOutputNode, self).__init__(
            qgraphics_item or QxNodeItem, parent_port
        )
        self.set_port_deletion_allowed(True)
        outpt = self.add_input("Next Output")
        outpt.view.setToolTip("Next Output")

    def get_widget_type(self, name):
        return self.model.get_widget_type(name)

    def add_input(self, name='input', multi_input=False, display_name=True,
                  color=None, locked=False, painter_func=None):
        # if self._inputs:
        #     raise PortRegistrationError(
        #         '"{}.add_input()" only ONE input is allowed for this node.'
        #         .format(self.__class__.__name__, self)
        #     )
        inpt = super(PortOutputNode, self).add_input(
            name=name,
            multi_input=multi_input,
            display_name=True,
            color=color,
            locked=locked,
            painter_func=None
        )
        if name != "Next Output":
            self.create_property(
                name=f"Output #{len(self.input_ports())-1}",
                value=name,
                widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            )
            if len(self._inputs) > 1:
                self.view._input_items.move_to_end(list(self.view._input_items.keys())[-2])
                self._inputs.append(self._inputs.pop(len(self._inputs)-2))
                self.update()
                self.view.draw_node()

        return inpt

    def on_input_connected(self, in_port, out_port):
        port_color = QxNodeBase._random_color_from_string(out_port.view.get_mx_port_type())
        in_port.color = port_color
        name = "out_" + out_port.node().name()
        if in_port.name() == "Next Output":
            while self.get_input(name):
                if "_" in name:
                    base, suffix = name.rsplit("_", 1)
                    try:
                        curnum = int(suffix)
                    except:
                        curnum = 0
                        base = name

                    name = base + "_" + str(curnum + 1)
                else:
                    name += "_1"

            in_port.model.name = name
            in_port.view.name = name
            in_port.view.multi_connection = False  # refresh tooltip
            text_item = self.view.get_input_text_item(in_port.view)
            text_item.setPlainText(name)
            out_port.model.connected_ports[self.id] = [name]
            self.model.inputs[name] = in_port.model
            self.create_property(
                name=f"Output #{len(self.input_ports())}",
                value=name,
                widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            )
            next_out = self.add_input("Next Output")
            next_out.view.setToolTip("Next Output")
            ng_port = self.graph.node.add_output(name, color=in_port.color)
        else:
            ng_port = self.graph.node.outputs()[in_port.name()]
            ng_port.color = port_color

        in_port.view.setToolTip(out_port.view.get_mx_port_type())
        ng_port.view.setToolTip(out_port.view.get_mx_port_type())

    def on_input_disconnected(self, in_port, out_port):
        if getattr(self.graph, "is_collapsing", False):
            return

        self.graph.node.get_output(in_port.name()).clear_connections()
        self.graph.node.delete_output(in_port.name())
        self.delete_input(in_port)
        self.refresh_output_props()

    def refresh_output_props(self):
        todel = [prop for prop in self.model._custom_prop if prop.startswith("Output #")]
        for prop in todel:
            if prop.startswith("Output #"):
                del self.model._custom_prop[prop]

        for idx, port in enumerate(self.input_ports()):
            if port.name() == "Next Output":
                continue

            self.create_property(
                name=f"Output #{idx+1}",
                value=port.name(),
                widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            )

    def refresh_port_colors(self):
        for port in self.input_ports():
            cports = port.connected_ports()
            if not cports:
                continue

            port.color = QxNodeBase._random_color_from_string(cports[0].view.get_mx_port_type())


class QxNodeItem(NodeItem):
    def __init__(self, name='node', parent=None):
        super(QxNodeItem, self).__init__(name, parent)

    def add_input(self, name='input', multi_port=False, display_name=True,
                  locked=False):
        """
        Adds a port qgraphics item into the node with the "port_type" set as
        IN_PORT.

        Args:
            name (str): name for the port.
            multi_port (bool): allow multiple connections.
            display_name (bool): display the port name.
            locked (bool): locked state.
            painter_func (function): custom paint function.

        Returns:
            PortItem: input port qgraphics item.
        """
        # custom start - overwrite portitem with own
        # if painter_func:
        #     port = CustomPortItem(self, painter_func)
        # else:
        #     port = PortItem(self)
        port = qx_port.QxPortItem(self)
        # custom end
        port.name = name
        port.port_type = PortTypeEnum.IN.value
        port.multi_connection = multi_port
        port.display_name = display_name
        port.locked = locked
        return self._add_port(port)

    def add_output(self, name='output', multi_port=False, display_name=True,
                   locked=False):
        """
        Adds a port qgraphics item into the node with the "port_type" set as
        OUT_PORT.

        Args:
            name (str): name for the port.
            multi_port (bool): allow multiple connections.
            display_name (bool): display the port name.
            locked (bool): locked state.
            painter_func (function): custom paint function.

        Returns:
            PortItem: output port qgraphics item.
        """
        # custom start - overwrite portitem with own
        # if painter_func:
        #     port = CustomPortItem(self, painter_func)
        # else:
        #     port = PortItem(self)
        port = qx_port.QxPortItem(self)
        # custom end
        port.name = name
        port.port_type = PortTypeEnum.OUT.value
        port.multi_connection = multi_port
        port.display_name = display_name
        port.locked = locked
        return self._add_port(port)

    def _delete_port(self, port, text):
        """
        Removes port item and port text from node.

        Args:
            port (PortItem): port object.
            text (QtWidgets.QGraphicsTextItem): port text object.
        """
        port.setParentItem(None)
        text.setParentItem(None)
        # custom start
        if self.scene():
            self.scene().removeItem(port)
            self.scene().removeItem(text)
        # custom end

        del port
        del text

    def mouseDoubleClickEvent(self, event):
        super(QxNodeItem, self).mouseDoubleClickEvent(event)
        if self.text_item.textInteractionFlags() & QtCore.Qt.TextSelectableByMouse:
            cursor = self.text_item.textCursor()
            cursor.setPosition(0)
            cursor.movePosition(QtGui.QTextCursor.Right, QtGui.QTextCursor.KeepAnchor, len(self.text_item.toPlainText()))
            self.text_item.setTextCursor(cursor)
            return


class QxGroupNodeItem(QxNodeItem):
    def __init__(self, name='group', parent=None):
        super(QxGroupNodeItem, self).__init__(name, parent)

    def add_input(self, name='input', multi_port=False, display_name=True,
                  locked=False):
        """
        Adds a port qgraphics item into the node with the "port_type" set as
        IN_PORT.

        Args:
            name (str): name for the port.
            multi_port (bool): allow multiple connections.
            display_name (bool): display the port name.
            locked (bool): locked state.
            painter_func (function): custom paint function.

        Returns:
            PortItem: input port qgraphics item.
        """
        # custom start - overwrite portitem with own
        # if painter_func:
        #     port = CustomPortItem(self, painter_func)
        # else:
        #     port = PortItem(self)
        port = qx_port.QxGroupNodePortItem(self)
        # custom end
        port.name = name
        port.port_type = PortTypeEnum.IN.value
        port.multi_connection = multi_port
        port.display_name = display_name
        port.locked = locked
        return self._add_port(port)

    def add_output(self, name='output', multi_port=False, display_name=True,
                   locked=False):
        """
        Adds a port qgraphics item into the node with the "port_type" set as
        OUT_PORT.

        Args:
            name (str): name for the port.
            multi_port (bool): allow multiple connections.
            display_name (bool): display the port name.
            locked (bool): locked state.
            painter_func (function): custom paint function.

        Returns:
            PortItem: output port qgraphics item.
        """
        # custom start - overwrite portitem with own
        # if painter_func:
        #     port = CustomPortItem(self, painter_func)
        # else:
        #     port = PortItem(self)
        port = qx_port.QxGroupNodePortItem(self)
        # custom end
        port.name = name
        port.port_type = PortTypeEnum.OUT.value
        port.multi_connection = multi_port
        port.display_name = display_name
        port.locked = locked
        return self._add_port(port)

    def mouseDoubleClickEvent(self, event):
        # Expand the Group Node on double click
        def get_node_of_node_item():
            for node in self.viewer().graph.all_nodes():
                if node.id == self.id:
                    return node
                
        name_rect = self.text_item.mapRectToItem(self, self.text_item.boundingRect())
        if name_rect.contains(event.pos()):
            super(QxGroupNodeItem, self).mouseDoubleClickEvent(event)
            return

        node = get_node_of_node_item()
        if event.button() == QtCore.Qt.LeftButton:
            node.expand()

        super(QxGroupNodeItem, self).mouseDoubleClickEvent(event)


def qx_node_from_mx_node_group_dict_generator(mx_node_defs):
    """_summary_

    Args:
        mx_node_defs (list of mx_defs): _description_

    Yields:
        QxNode: _description_
    """
    grp_dict = mx_node.get_mx_node_group_dict(mx_node_defs)
    for mx_node_group, mx_node_def_name_dict in grp_dict.items():
        for mx_node_def_name, mx_node_defs in mx_node_def_name_dict.items():
            label = f"{mx_node_group.capitalize()}.{mx_node_def_name.capitalize()}"
            qx_node = type(
                mx_node_def_name.capitalize(),
                (QxNode,),
                {
                    "NODE_NAME": mx_node_def_name.capitalize(),
                    "__identifier__": mx_node_group.capitalize(),
                    "__label__": label,
                    "possible_mx_defs": mx_node_defs,
                },
            )
            yield qx_node
