from qtpy import QtGui, QtCore  # type: ignore
import NodeGraphQt

# from NodeGraphQt.custom_widgets import properties
from NodeGraphQt.constants import PortEnum

ACTIVE_PORT_COLOR = "#1898ae"
HOVER_PORT_COLOR = "#e0e0e0"
INVALID_COLOR = "#c93d30"
CONNECTED_COLOR = "#ffffff"

ADDITIONAL_COMPATIBLE_PORT_TYPES = {
    "vector3": ["color3", ],
    "color3": ["vector3", ],
    "vector4": ["color4", ],
    "color4": ["color4", ],
    "vector2": ["float", ],
}


class QxPortItem(NodeGraphQt.qgraphics.node_base.PortItem):
    def get_mx_port_type(self):
        if not hasattr(self.node, "basenode"):
            return

        if self.port_type == "in":
            mx_port_type = self.node.basenode.current_mx_def.getActiveInput(self.name).getType()
        else:
            mx_port_type = self.node.basenode.current_mx_def.getActiveOutput(self.name).getType()

        return mx_port_type

    def get_port_types(self, current=False):
        has_connections = False
        ports = self.node.inputs + self.node.outputs
        for port in ports:
            if port == self:
                continue

            if port.connected_pipes:
                # if the current node has connections, we don't consider changing the node type
                has_connections = True
                break

        if has_connections or current:
            if hasattr(self.node.basenode, "current_mx_def"):
                if self.port_type == "in":
                    mxport = self.node.basenode.current_mx_def.getActiveInput(self.name)
                else:
                    mxport = self.node.basenode.current_mx_def.getActiveOutput(self.name)
            else:
                return "color3"

            if current:
                return mxport.getType()

            port_types = [mxport.getType()]
        else:
            port_types = []
            for mxdef in self.node.basenode.possible_mx_defs.values():
                if self.port_type == "in":
                    mxport = mxdef.getActiveInput(self.name)
                else:
                    mxport = mxdef.getActiveOutput(self.name)

                if not mxport:
                    continue

                port_type = mxport.getType()
                if port_type not in port_types:
                    port_types.append(port_type)

        return port_types

    def refresh_tool_tip(self):
        ttip = self.get_port_types(current=True)
        self.setToolTip(ttip)

    def paint(self, painter, option, widget):
        """
        Draws the circular port.

        Args:
            painter (QtGui.QPainter): painter used for drawing the item.
            option (QtGui.QStyleOptionGraphicsItem):
                used to describe the parameters needed to draw.
            widget (QtWidgets.QWidget): not used.
        """
        painter.save()

        #  display falloff collision for debugging
        # ----------------------------------------------------------------------
        # pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 80), 0.8)
        # pen.setStyle(QtCore.Qt.DotLine)
        # painter.setPen(pen)
        # painter.drawRect(self.boundingRect())
        # ----------------------------------------------------------------------

        rect_w = self._width / 1.8
        rect_h = self._height / 1.8
        rect_x = self.boundingRect().center().x() - (rect_w / 2)
        rect_y = self.boundingRect().center().y() - (rect_h / 2)
        port_rect = QtCore.QRectF(rect_x, rect_y, rect_w, rect_h)

        # TODO: Find a better way to get the view. This only allows one.
        view = self.scene().views()[0]
        graph = self.node.viewer().graph
        valid_connection = True
        if view._LIVE_PIPE.isVisible() and view._start_port:
            # core = self.node.scene().views()[0].parent().window().core
            if self.port_type == "out":
                ptypes = "outputs"
            elif self.port_type == "in":
                ptypes = "inputs"

            current_port = getattr(
                graph.get_node_by_id(self.node.id), ptypes
            )()[self.name]
            if view._start_port.port_type == "out":
                ptypes = "outputs"
            elif view._start_port.port_type == "in":
                ptypes = "inputs"

            start_port = getattr(
                graph.get_node_by_id(view._start_port.node.id), ptypes
            )()[view._start_port.name]

            # Port check only needed if both ports are available
            if all((current_port, start_port)):
                valid_connection = are_ports_compatible(
                    current_port, start_port
                )

        # TODO do another way
        self._locked = False
        if self._hovered:
            color = QtGui.QColor(HOVER_PORT_COLOR)
            border_color = QtGui.QColor(HOVER_PORT_COLOR)
            if not valid_connection:
                border_color = QtGui.QColor(INVALID_COLOR)
                color = QtGui.QColor(INVALID_COLOR)
                # TODO do another way
                self._locked = True

        if self.connected_pipes:
            color = QtGui.QColor(*self.color)
            border_color = QtGui.QColor(*self.color)
        else:
            color = QtGui.QColor(*self.color)
            border_color = QtGui.QColor(*self.color)

        pen = QtGui.QPen(border_color, 0)
        painter.setPen(pen)
        painter.setBrush(color)
        painter.drawEllipse(port_rect)

        if self.connected_pipes:
            border_color = QtGui.QColor(CONNECTED_COLOR)
            painter.setBrush(border_color)
            w = port_rect.width() / 2.5
            h = port_rect.height() / 2.5
            rect = QtCore.QRectF(
                port_rect.center().x() - w / 2,
                port_rect.center().y() - h / 2,
                w,
                h,
            )
            # pen = QtGui.QPen(border_color, 1.6)
            # painter.setPen(pen)
            painter.setBrush(border_color)
            painter.drawEllipse(rect)

        if self._hovered:
            color = QtGui.QColor(255, 255, 255, 70)
            # pen = QtGui.QPen(color, 1.8)
            # painter.setPen(pen)
            painter.setBrush(color)
            painter.drawEllipse(port_rect)
        painter.restore()


class QxGroupNodePortItem(QxPortItem):
    pass


def are_ports_compatible(port1, port2):
    # If both ports are inputs or outputs, we can exit straight away
    if port1.view.port_type == port2.view.port_type:
        return False
    
    if not isinstance(port1, QxPortItem) or not isinstance(port2, QxPortItem):
        return True

    port1_type = port1.view.get_mx_port_type()
    port2_type = port2.view.get_mx_port_type()

    compatible_port1_types = [port1_type]
    if port1_type in ADDITIONAL_COMPATIBLE_PORT_TYPES:
        compatible_port1_types.extend(ADDITIONAL_COMPATIBLE_PORT_TYPES[port1_type])

    compatible_port2_types = [port2_type]
    if port2_type in ADDITIONAL_COMPATIBLE_PORT_TYPES:
        compatible_port2_types.extend(ADDITIONAL_COMPATIBLE_PORT_TYPES[port2_type])

    compatible = not set(compatible_port1_types).isdisjoint(compatible_port2_types)

    return compatible
