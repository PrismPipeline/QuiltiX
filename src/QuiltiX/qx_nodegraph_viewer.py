from QuiltiX.qx_nodegraph_tabsearch import QxTabSearchWidget


import NodeGraphQt
from NodeGraphQt.qgraphics.node_abstract import AbstractNodeItem
from NodeGraphQt.qgraphics.port import PortItem
from qtpy import QtCore, QtGui  # type: ignore


import math
import os


class QxNodeGraphViewer(NodeGraphQt.widgets.viewer.NodeViewer):
    def __init__(self, node_graph, parent=None, undo_stack=None):
        super(QxNodeGraphViewer, self).__init__(parent, undo_stack)

        self._search_widget = QxTabSearchWidget()
        self._search_widget.search_submitted.connect(self._on_search_submitted)
        self.data_dropped.connect(self.on_data_dropped)

        # Added self.graph so it is always available for function calls
        self.graph = node_graph

    def on_data_dropped(self, data, pos):
        img_count = 0
        for url in data.urls():
            local_path = url.toLocalFile()
            if os.path.isdir(local_path):
                contents = os.listdir(local_path)
                for content in contents:
                    if content.endswith(".mtlx"):
                        local_path = os.path.join(local_path, content)
                        break

            elif local_path.endswith(".mtlx"):
                self.graph.load_graph_from_mx_file(local_path)
            elif os.path.splitext(local_path)[1] in [".jpg", ".png", ".jpeg", ".exr", ".tif"]:
                self.graph.load_image_file(local_path, yoffset=300*img_count)
                img_count += 1

    def sceneMouseMoveEvent(self, event):
        # paint valid color indicator when dragging a connection and hovering over port of other node
        if self._LIVE_PIPE.isVisible():
            for item in self.scene().items(event.scenePos()):
                if isinstance(item, PortItem):
                    end_port = item
                    if (
                        hasattr(self, "porth")
                        and self.porth
                        and self.porth != end_port
                    ):
                        self.porth.hovered = False
                        self.porth.update()

                    end_port.hovered = True
                    end_port.update()
                    self.porth = end_port
                    break
            else:
                if hasattr(self, "porth") and self.porth:
                    self.porth.hovered = False
                    self.porth.update()
                    self.porth = None

        super(QxNodeGraphViewer, self).sceneMouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.LMB_state = True
        elif event.button() == QtCore.Qt.RightButton:
            self.RMB_state = True
        elif event.button() == QtCore.Qt.MiddleButton:
            self.MMB_state = True

        self._origin_pos = event.pos()
        self._previous_pos = event.pos()
        (self._prev_selection_nodes,
         self._prev_selection_pipes) = self.selected_items()

        # close tab search
        if self._search_widget.isVisible():
            self.tab_search_toggle()

        # cursor pos.
        map_pos = self.mapToScene(event.pos())

        # pipe slicer enabled.
        # custom start - change slicer shortcut
        slicer_mode = getattr(self, "keyY_pressed", None)
        # custom end
        if slicer_mode:
            self._SLICER_PIPE.draw_path(map_pos, map_pos)
            self._SLICER_PIPE.setVisible(True)
            return

        # pan mode.
        if self.ALT_state:
            return

        items = self._items_near(map_pos, None, 20, 20)
        nodes = [i for i in items if isinstance(i, AbstractNodeItem)]
        # pipes = [i for i in items if isinstance(i, PipeItem)]

        if nodes:
            self.MMB_state = False

        # toggle extend node selection.
        if self.LMB_state:
            if self.SHIFT_state:
                for node in nodes:
                    node.selected = not node.selected
            elif self.CTRL_state:
                for node in nodes:
                    node.selected = False

        # update the recorded node positions.
        self._node_positions.update(
            {n: n.xy_pos for n in self.selected_nodes()}
        )

        # show selection selection marquee.
        if self.LMB_state and not items:
            rect = QtCore.QRect(self._previous_pos, QtCore.QSize())
            rect = rect.normalized()
            map_rect = self.mapToScene(rect).boundingRect()
            self.scene().update(map_rect)
            self._rubber_band.setGeometry(rect)
            self._rubber_band.isActive = True

        if self.LMB_state and (self.SHIFT_state or self.CTRL_state):
            return

        if not self._LIVE_PIPE.isVisible():
            super(NodeGraphQt.widgets.viewer.NodeViewer, self).mousePressEvent(event)

    # custom start - slice shortcut
    def keyPressEvent(self, event):
        key = event.key()
        if key == QtCore.Qt.Key_Y:
            self.keyY_pressed = True

        super(QxNodeGraphViewer, self).keyPressEvent(event)
    # custom end

    # custom start - slice shortcut
    def keyReleaseEvent(self, event):
        key = event.key()
        if key == QtCore.Qt.Key_Y:
            self.keyY_pressed = False

        super(QxNodeGraphViewer, self).keyPressEvent(event)
    # custom end

    def mouseMoveEvent(self, event):
        # custom start - slice shortcut
        if getattr(self, "keyY_pressed", None):
        # custom end
            if self.LMB_state and self._SLICER_PIPE.isVisible():
                p1 = self._SLICER_PIPE.path().pointAtPercent(0)
                p2 = self.mapToScene(self._previous_pos)
                self._SLICER_PIPE.draw_path(p1, p2)
                self._SLICER_PIPE.show()
            self._previous_pos = event.pos()
            super(NodeGraphQt.widgets.viewer.NodeViewer, self).mouseMoveEvent(event)
            return

        if self.MMB_state and self.ALT_state:
            pos_x = (event.x() - self._previous_pos.x())
            zoom = 0.1 if pos_x > 0 else -0.1
            self._set_viewer_zoom(zoom, 0.05, pos=event.pos())
        elif self.MMB_state or (self.LMB_state and self.ALT_state):
            previous_pos = self.mapToScene(self._previous_pos)
            current_pos = self.mapToScene(event.pos())
            delta = previous_pos - current_pos
            self._set_viewer_pan(delta.x(), delta.y())

        if self.LMB_state and self._rubber_band.isActive:
            rect = QtCore.QRect(self._origin_pos, event.pos()).normalized()
            # if the rubber band is too small, do not show it.
            if max(rect.width(), rect.height()) > 5:
                if not self._rubber_band.isVisible():
                    self._rubber_band.show()
                map_rect = self.mapToScene(rect).boundingRect()
                path = QtGui.QPainterPath()
                path.addRect(map_rect)
                self._rubber_band.setGeometry(rect)
                self.scene().setSelectionArea(path)
                self.scene().update(map_rect)

                if self.SHIFT_state or self.CTRL_state:
                    nodes, pipes = self.selected_items()

                    for node in self._prev_selection_nodes:
                        node.selected = True

                    if self.CTRL_state:
                        for pipe in pipes:
                            pipe.setSelected(False)
                        for node in nodes:
                            node.selected = False

        elif self.LMB_state:
            self.COLLIDING_state = False
            nodes, pipes = self.selected_items()
            if len(nodes) == 1:
                node = nodes[0]
                [p.setSelected(False) for p in pipes]

                if self.pipe_collision:
                    colliding_pipes = [
                        i for i in node.collidingItems()
                        if isinstance(i, PipeItem) and i.isVisible()
                    ]
                    for pipe in colliding_pipes:
                        if not pipe.input_port:
                            continue
                        port_node_check = all([
                            not pipe.input_port.node is node,
                            not pipe.output_port.node is node
                        ])
                        if port_node_check:
                            pipe.setSelected(True)
                            self.COLLIDING_state = True
                            break

        self._previous_pos = event.pos()
        super(NodeGraphQt.widgets.viewer.NodeViewer, self).mouseMoveEvent(event)

    def apply_live_connection(self, event):
        """
        triggered mouse press/release event for the scene.
        - verifies the live connection pipe.
        - makes a connection pipe if valid.
        - emits the "connection changed" signal.

        Args:
            event (QtWidgets.QGraphicsSceneMouseEvent):
                The event handler from the QtWidgets.QGraphicsScene
        """
        if not self._LIVE_PIPE.isVisible():
            return

        self._start_port.hovered = False

        # find the end port.
        end_port = None
        for item in self.scene().items(event.scenePos()):
            if isinstance(item, PortItem):
                end_port = item
                break

        connected = []
        disconnected = []

        # if port disconnected from existing pipe.
        if end_port is None:
            if self._detached_port and not self._LIVE_PIPE.shift_selected:
                dist = math.hypot(self._previous_pos.x() - self._origin_pos.x(),
                                  self._previous_pos.y() - self._origin_pos.y())
                if dist <= 2.0:  # cursor pos threshold.
                    self.establish_connection(self._start_port,
                                              self._detached_port)
                    self._detached_port = None
                else:
                    disconnected.append((self._start_port, self._detached_port))
                    self.connection_changed.emit(disconnected, connected)
            # custom start - connect node
            elif not self._detached_port:
                if self.underMouse():
                    self._search_widget.port_to_connect = self._start_port
                    filteredNodes = self.filter_compatible_nodes(self._start_port)
                    if filteredNodes:
                        self.rebuild_tab_search()
                        self.tab_search_set_nodes(filteredNodes)
                        self.tab_search_toggle()
                        self.rebuild_tab_search()

            # custom end

            self._detached_port = None
            self.end_live_connection()
            return

        else:
            if self._start_port is end_port:
                return

        # restore connection check.
        restore_connection = any([
            # if the end port is locked.
            end_port.locked,
            # if same port type.
            end_port.port_type == self._start_port.port_type,
            # if connection to itself.
            end_port.node == self._start_port.node,
            # if end port is the start port.
            end_port == self._start_port,
            # if detached port is the end port.
            self._detached_port == end_port
        ])
        if restore_connection:
            if self._detached_port:
                to_port = self._detached_port or end_port
                self.establish_connection(self._start_port, to_port)
                self._detached_port = None
            self.end_live_connection()
            return

        # end connection if starting port is already connected.
        if self._start_port.multi_connection and \
                self._start_port in end_port.connected_ports:
            self._detached_port = None
            self.end_live_connection()
            return

        # register as disconnected if not acyclic.
        if self.acyclic and not self.acyclic_check(self._start_port, end_port):
            if self._detached_port:
                disconnected.append((self._start_port, self._detached_port))

            self.connection_changed.emit(disconnected, connected)

            self._detached_port = None
            self.end_live_connection()
            return

        # make connection.
        if not end_port.multi_connection and end_port.connected_ports:
            dettached_end = end_port.connected_ports[0]
            disconnected.append((end_port, dettached_end))

        if self._detached_port:
            disconnected.append((self._start_port, self._detached_port))

        connected.append((self._start_port, end_port))

        self.connection_changed.emit(disconnected, connected)

        self._detached_port = None
        self.end_live_connection()

    def setStyleSheet(self, stylesheet):
        super(QxNodeGraphViewer, self).setStyleSheet(stylesheet)
        self._search_setStyleSheet(stylesheet)
        self._search_widget.line_edit.setStyleSheet(stylesheet)
        # TODO? needed?
        # self._menu_stylesheet = stylesheet

    def filter_compatible_nodes(self, port):
        nodes = self.graph.node_factory.names
        if not hasattr(port, "get_port_types") or not hasattr(port.node, "basenode"):
            return nodes

        filtered_nodes = {}
        white_listed = ["Nodegraph"]
        for node in nodes:
            if node in white_listed or port.node.type_ == "nodes.group.GenericQxGroupNode":
                filtered_nodes[node] = nodes[node]
                continue

            nodeDef = self.graph.node_factory.nodes[nodes[node][0]]
            if not hasattr(nodeDef, "output_ports"):
                continue

            if port.port_type == "in":
                output_types = []
                for mxdef in nodeDef.possible_mx_defs.values():
                    outputs = mxdef.getActiveOutputs()
                    if not outputs:
                        continue

                    output_types += [output.getType() for output in outputs]

                input_types = port.get_port_types()
            else:
                input_types = []
                for mxdef in nodeDef.possible_mx_defs.values():
                    mx_inputs = mxdef.getActiveInputs()
                    if not mx_inputs:
                        continue

                    input_types += [mx_input.getType() for mx_input in mx_inputs]

                output_types = port.get_port_types()

            compatible = False
            for input_type in input_types:
                if input_type in output_types:
                    compatible = True

            if compatible:
                filtered_nodes[node] = nodes[node]

        return filtered_nodes

    def tab_search_toggle(self):
        # Skip resizing/moving

        # custom start
        # state = self._search_widget.isVisible()
        # if not state:
        #     self._search_widget.setVisible(state)
        #     self.setFocus()
        #     return

        # pos = self._previous_pos
        # rect = self._search_widget.rect()
        # new_pos = QtCore.QPoint(int(pos.x() - rect.width() / 2),
        #                         int(pos.y() - rect.height() / 2))
        # self._search_widget.move(new_pos)
        # self._search_widget.setVisible(state)
        # self._search_widget.setFocus()

        # rect = self.mapToScene(rect).boundingRect()
        # self.scene().update(rect)

        state = self._search_widget.isVisible()
        self._search_widget.setVisible(state)
        self._search_widget.setFocus()