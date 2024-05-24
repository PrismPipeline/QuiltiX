import QuiltiX.qx_node as qx_node_module
from QuiltiX.qx_nodegraph import QxNodeGraph

from NodeGraphQt.base.commands import PortConnectedCmd
from NodeGraphQt.base.menu import NodeGraphMenu
from NodeGraphQt.constants import LayoutDirectionEnum, PortTypeEnum
from NodeGraphQt.errors import NodeDeletionError
from NodeGraphQt.nodes.group_node import GroupNode
from NodeGraphQt.nodes.port_node import PortInputNode, PortOutputNode
from NodeGraphQt.widgets.node_graph import SubGraphWidget
from qtpy import QtWidgets  # type: ignore


import copy


class QxSubNodeGraph(QxNodeGraph):
    """
    The ``SubGraph`` class is just like the ``NodeGraph`` but is the main
    controller for managing the expanded node graph for a group node.

    Inherited from: :class:`NodeGraphQt.NodeGraph`

    .. image:: _images/sub_graph.png
        :width: 70%

    -
    """

    def __init__(self, parent=None, node=None, node_factory=None, **kwargs):
        """
        Args:
            parent (object): object parent.
            node (GroupNode): group node related to this sub graph.
            node_factory (NodeFactory): override node factory.
            **kwargs (dict): additional kwargs.
        """
        # custom start - changed super args
        super(QxSubNodeGraph, self).__init__(
            parent, node_factory=node_factory, **kwargs
        )
        # custom end

        # sub graph attributes.
        self._node = node
        self._parent_graph = parent
        self._subviewer_widget = None

        if self._parent_graph.is_root:
            self._initialized_graphs = [self]
            self._sub_graphs[self._node.id] = self
        else:
            # delete attributes if not top level sub graph.
            del self._widget
            del self._sub_graphs

        # clone context menu from the parent node graph.
        self._clone_context_menu_from_parent()


    def __repr__(self):
        return '<{}("{}") object at {}>'.format(
            self.__class__.__name__, self._node.name(), hex(id(self)))

    def _register_builtin_nodes(self):
        """
        Register the default builtin nodes to the :meth:`NodeGraph.node_factory`
        """
        return

    def _clone_context_menu_from_parent(self):
        """
        Clone the context menus from the parent node graph.
        """
        graph_menu = self.get_context_menu('graph')
        parent_menu = self.parent_graph.get_context_menu('graph')
        parent_viewer = self.parent_graph.viewer()
        excl_actions = [parent_viewer.qaction_for_undo(),
                        parent_viewer.qaction_for_redo()]

        def clone_menu(menu, menu_to_clone):
            """
            Args:
                menu (NodeGraphQt.NodeGraphMenu):
                menu_to_clone (NodeGraphQt.NodeGraphMenu):
            """
            sub_items = []
            for item in menu_to_clone.get_items():
                if item is None:
                    menu.add_separator()
                    continue
                name = item.name()
                if isinstance(item, NodeGraphMenu):
                    sub_menu = menu.add_menu(name)
                    sub_items.append([sub_menu, item])
                    continue

                if item in excl_actions:
                    continue

                menu.add_command(
                    name,
                    func=item.slot_function,
                    shortcut=item.qaction.shortcut()
                )

            for sub_menu, to_clone in sub_items:
                clone_menu(sub_menu, to_clone)

        # duplicate the menu items.
        clone_menu(graph_menu, parent_menu)

    def _build_port_nodes(self):
        """
        Build the corresponding input & output nodes from the parent node ports
        and remove any port nodes that are outdated..

        Returns:
             tuple(dict, dict): input nodes, output nodes.
        """
        node_layout_direction = self._viewer.get_layout_direction()

        input_port_nodes = self.get_input_port_nodes()
        if input_port_nodes:
            input_node = input_port_nodes[0]
        else:
            # build the parent input port nodes.
            input_node = qx_node_module.QxPortInputNode()
            input_node.NODE_NAME = "Inputs"
            input_node.model.set_property('name', "Inputs")
            self.add_node(input_node, selected=False, push_undo=False)
            x, y = input_node.pos()
            if node_layout_direction is LayoutDirectionEnum.HORIZONTAL.value:
                x -= 500
            elif node_layout_direction is LayoutDirectionEnum.VERTICAL.value:
                y -= 500
            input_node.set_property('pos', [x, y], push_undo=False)

            for port in self.node.input_ports():
                input_node.add_output(port.name())

        output_port_nodes = self.get_output_port_nodes()
        if input_port_nodes:
            output_node = output_port_nodes[0]
        else:
            # build the parent output port nodes.
            output_node = qx_node_module.QxPortOutputNode()
            output_node.NODE_NAME = "Outputs"
            output_node.model.set_property('name', "Outputs")
            self.add_node(output_node, selected=False, push_undo=False)
            x, y = output_node.pos()
            if node_layout_direction is LayoutDirectionEnum.HORIZONTAL.value:
                x += 500
            elif node_layout_direction is LayoutDirectionEnum.VERTICAL.value:
                y += 500
            output_node.set_property('pos', [x, y], push_undo=False)

            for port in self.node.output_ports():
                output_node.add_input(port.name())

        return {input_node.name(): input_node}, {output_node.name(): output_node}

    def _deserialize(self, data, relative_pos=False, pos=None):
        """
        deserialize node data.
        (used internally by the node graph)

        Args:
            data (dict): node data.
            relative_pos (bool): position node relative to the cursor.
            pos (tuple or list): custom x, y position.

        Returns:
            list[NodeGraphQt.Nodes]: list of node instances.
        """
        # update node graph properties.
        for attr_name, attr_value in data.get('graph', {}).items():
            if attr_name == 'acyclic':
                self.set_acyclic(attr_value)
            elif attr_name == 'pipe_collision':
                self.set_pipe_collision(attr_value)

        # build the port input & output nodes here.
        input_nodes, output_nodes = self._build_port_nodes()

        # build the nodes.
        nodes = {}
        for n_id, n_data in data.get('nodes', {}).items():
            identifier = n_data['type_']
            name = n_data.get('name')
            if identifier == PortInputNode.type_:
                nodes[n_id] = input_nodes[name]
                nodes[n_id].set_pos(*(n_data.get('pos') or [0, 0]))
                continue
            elif identifier == "Inputs.QxPortInputNode":
                nodes[n_id] = input_nodes[name]
                nodes[n_id].set_pos(*(n_data.get('pos') or [0, 0]))
                continue
            elif identifier == PortOutputNode.type_:
                nodes[n_id] = output_nodes[name]
                nodes[n_id].set_pos(*(n_data.get('pos') or [0, 0]))
                continue
            elif identifier == "Outputs.QxPortOutputNode":
                nodes[n_id] = output_nodes[name]
                nodes[n_id].set_pos(*(n_data.get('pos') or [0, 0]))
                continue

            node = self._node_factory.create_node_instance(identifier)
            if not node:
                continue

            node.NODE_NAME = name or node.NODE_NAME
            # set properties.
            for prop in node.model.properties.keys():
                if prop in n_data.keys():
                    node.model.set_property(prop, n_data[prop])

            # set custom properties.
            for prop, val in n_data.get('custom', {}).items():
                # custom start
                if prop == "type":
                    node.change_type(val)
                # custom end
                node.model.set_property(prop, val)

            nodes[n_id] = node
            self.add_node(node, n_data.get('pos'))

            if n_data.get('port_deletion_allowed', None):
                node.set_ports({
                    'input_ports': n_data['input_ports'],
                    'output_ports': n_data['output_ports']
                })

        # build the connections.
        for connection in data.get('connections', []):
            nid, pname = connection.get('in', ('', ''))
            in_node = nodes.get(nid)
            if not in_node:
                continue
            in_port = in_node.inputs().get(pname) if in_node else None

            nid, pname = connection.get('out', ('', ''))
            out_node = nodes.get(nid)
            if not out_node:
                continue
            out_port = out_node.outputs().get(pname) if out_node else None

            if in_port and out_port:
                self._undo_stack.push(PortConnectedCmd(in_port, out_port))

        node_objs = list(nodes.values())
        if relative_pos:
            self._viewer.move_nodes([n.view for n in node_objs])
            [setattr(n.model, 'pos', n.view.xy_pos) for n in node_objs]
        elif pos:
            self._viewer.move_nodes([n.view for n in node_objs], pos=pos)
            [setattr(n.model, 'pos', n.view.xy_pos) for n in node_objs]

        return node_objs

    def _on_navigation_changed(self, node_id, rm_node_ids):
        """
        Slot when the node navigation widget has changed.

        Args:
            node_id (str): selected group node id.
            rm_node_ids (list[str]): list of group node id to remove.
        """
        # collapse child sub graphs.
        for rm_node_id in rm_node_ids:
            child_node = self.sub_graphs[rm_node_id].node
            self.collapse_group_node(child_node)

        # show the selected node id sub graph.
        sub_graph = self.sub_graphs.get(node_id)
        if sub_graph:
            self.widget.show_viewer(sub_graph.subviewer_widget)
            sub_graph.viewer().setFocus()

    @property
    def is_root(self):
        """
        Returns if the node graph controller is the main root graph.

        Returns:
            bool: true is the node graph is root.
        """
        return False

    @property
    def sub_graphs(self):
        """
        Returns expanded group node sub graphs.

        Returns:
            dict: {<node_id>: <sub_graph>}
        """
        if self.parent_graph.is_root:
            return self._sub_graphs
        return self.parent_graph.sub_graphs

    @property
    def initialized_graphs(self):
        """
        Returns a list of the sub graphs in the order they were initialized.

        Returns:
            list[NodeGraphQt.SubGraph]: list of sub graph objects.
        """
        if self._parent_graph.is_root:
            return self._initialized_graphs
        return self._parent_graph.initialized_graphs

    @property
    def widget(self):
        """
        The sub graph widget from the top most sub graph.

        Returns:
            SubGraphWidget: node graph widget.
        """
        if self.parent_graph.is_root:
            if self._widget is None:
                #custom start - add graph
                self._widget = SubGraphWidget(graph=self)
                # custom end
                self._widget.add_viewer(self.subviewer_widget,
                                        self.node.name(),
                                        self.node.id)
                # connect the navigator widget signals.
                navigator = self._widget.navigator
                navigator.navigation_changed.connect(
                    self._on_navigation_changed
                )
            return self._widget
        return self.parent_graph.widget

    @property
    def navigation_widget(self):
        """
        The navigation widget from the top most sub graph.

        Returns:
            NodeNavigationWidget: navigation widget.
        """
        if self.parent_graph.is_root:
            return self.widget.navigator
        return self.parent_graph.navigation_widget

    @property
    def subviewer_widget(self):
        """
        The widget to the sub graph.

        Returns:
            PySide2.QtWidgets.QWidget: node graph widget.
        """
        if self._subviewer_widget is None:
            self._subviewer_widget = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(self._subviewer_widget)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(1)
            layout.addWidget(self._viewer)
        return self._subviewer_widget

    @property
    def parent_graph(self):
        """
        The parent node graph controller.

        Returns:
            NodeGraphQt.NodeGraph or NodeGraphQt.SubGraph: parent graph.
        """
        return self._parent_graph

    @property
    def node(self):
        """
        Returns the parent node to the sub graph.

        .. image:: _images/group_node.png
            :width: 250px

        Returns:
            NodeGraphQt.GroupNode: group node.
        """
        return self._node

    def delete_node(self, node, push_undo=True):
        """
        Remove the node from the node sub graph.

        Note:
            :class:`.PortInputNode` & :class:`.PortOutputNode` can't be deleted
            as they are connected to a :class:`.Port` to remove these port nodes
            see :meth:`BaseNode.delete_input`, :meth:`BaseNode.delete_output`.

        Args:
            node (NodeGraphQt.BaseNode): node object.
            push_undo (bool): register the command to the undo stack. (default: True)
        """
        port_nodes = self.get_input_port_nodes() + self.get_output_port_nodes()
        if node in port_nodes and node.parent_port is not None:
            # note: port nodes can only be deleted by deleting the parent
            #       port object.
            raise NodeDeletionError(
                '{} can\'t be deleted as it is attached to a port!'.format(node)
            )
        # custom start - change super
        super().delete_node(node, push_undo=push_undo)
        # custom end

    def delete_nodes(self, nodes, push_undo=True):
        """
        Remove a list of specified nodes from the node graph.

        Args:
            nodes (list[NodeGraphQt.BaseNode]): list of node instances.
            push_undo (bool): register the command to the undo stack. (default: True)
        """
        if not nodes:
            return

        port_nodes = self.get_input_port_nodes() + self.get_output_port_nodes()
        for node in nodes:
            if node in port_nodes and node.parent_port is not None:
                # note: port nodes can only be deleted by deleting the parent
                #       port object.
                raise NodeDeletionError(
                    '{} can\'t be deleted as it is attached to a port!'
                    .format(node)
                )

        # custom start - change super
        super().delete_nodes(nodes, push_undo=push_undo)
        # custom end

    def collapse_graph(self, clear_session=True):
        """
        Collapse the current sub graph and hide its widget.

        Args:
            clear_session (bool): clear the current session.
        """
        # update the group node.
        serialized_session = self.serialize_session()
        self.node.set_sub_graph_session(serialized_session)

        # close the visible widgets.
        if self._undo_view:
            self._undo_view.close()

        if self._subviewer_widget:
            self.widget.hide_viewer(self._subviewer_widget)

        if clear_session:
            self.clear_session()

    def expand_group_node(self, node):
        """
        Expands a group node session in current sub view.

        Args:
            node (NodeGraphQt.GroupNode): group node.

        Returns:
            SubGraph: sub node graph used to manage the group node session.
        """
        assert isinstance(node, GroupNode), 'node must be a GroupNode instance.'
        if self._subviewer_widget is None:
            raise RuntimeError('SubGraph.widget not initialized!')

        self.viewer().clear_key_state()
        self.viewer().clearFocus()

        if node.id in self.sub_graphs:
            sub_graph_viewer = self.sub_graphs[node.id].viewer()
            sub_graph_viewer.setFocus()
            return self.sub_graphs[node.id]

        # collapse expanded child sub graphs.
        group_ids = [n.id for n in self.all_nodes() if isinstance(n, GroupNode)]
        for grp_node_id, grp_sub_graph in self.sub_graphs.items():
            # collapse current group node.
            if grp_node_id in group_ids:
                grp_node = self.get_node_by_id(grp_node_id)
                self.collapse_group_node(grp_node)

            # close the widgets
            grp_sub_graph.collapse_graph(clear_session=False)

        # build new sub graph.
        node_factory = copy.deepcopy(self.node_factory)

        # custom start - replace supgraph
        sub_graph = QxSubNodeGraph(self,
                             node=node,
                             node_factory=node_factory,
                             layout_direction=self.layout_direction())
        # custom end

        # populate the sub graph.
        serialized_session = node.get_sub_graph_session()
        sub_graph.deserialize_session(serialized_session)

        # open new sub graph view.
        self.widget.add_viewer(sub_graph.subviewer_widget,
                               node.name(),
                               node.id)

        # store the references.
        self.sub_graphs[node.id] = sub_graph
        self.initialized_graphs.append(sub_graph)

        return sub_graph

    def collapse_group_node(self, node):
        """
        Collapse a group node session and it's expanded child sub graphs.

        Args:
            node (NodeGraphQt.GroupNode): group node.
        """
        # update the references.
        sub_graph = self.sub_graphs.pop(node.id, None)
        if not sub_graph:
            return

        init_idx = self.initialized_graphs.index(sub_graph) + 1
        for sgraph in reversed(self.initialized_graphs[init_idx:]):
            self.initialized_graphs.remove(sgraph)

        # collapse child sub graphs here.
        child_ids = [
            n.id for n in sub_graph.all_nodes() if isinstance(n, GroupNode)
        ]
        for child_id in child_ids:
            if self.sub_graphs.get(child_id):
                child_graph = self.sub_graphs.pop(child_id)
                child_graph.collapse_graph(clear_session=True)
                # remove child viewer widget.
                self.widget.remove_viewer(child_graph.subviewer_widget)

        with self.get_root_graph().block_save():
            self.is_collapsing = True
            sub_graph.collapse_graph(clear_session=True)
            self.is_collapsing = False

        self.widget.remove_viewer(sub_graph.subviewer_widget)

    def get_input_port_nodes(self):
        """
        Return all the port nodes related to the group node input ports.

        .. image:: _images/port_in_node.png
            :width: 150px

        -

        See Also:
            :meth:`NodeGraph.get_nodes_by_type`,
            :meth:`SubGraph.get_output_port_nodes`

        Returns:
            list[NodeGraphQt.PortInputNode]: input nodes.
        """
        return self.get_nodes_by_type(qx_node_module.QxPortInputNode.type_)

    def get_output_port_nodes(self):
        """
        Return all the port nodes related to the group node output ports.

        .. image:: _images/port_out_node.png
            :width: 150px

        -

        See Also:
            :meth:`NodeGraph.get_nodes_by_type`,
            :meth:`SubGraph.get_input_port_nodes`

        Returns:
            list[NodeGraphQt.PortOutputNode]: output nodes.
        """
        return self.get_nodes_by_type(qx_node_module.QxPortOutputNode.type_)

    def get_node_by_port(self, port):
        """
        Returns the node related to the parent group node port object.

        Args:
            port (NodeGraphQt.Port): parent node port object.

        Returns:
            PortInputNode or PortOutputNode: port node object.
        """
        func_type = {
            PortTypeEnum.IN.value: self.get_input_port_nodes(),
            PortTypeEnum.OUT.value: self.get_output_port_nodes()
        }
        for n in func_type.get(port.type_(), []):
            if port == n.parent_port:
                return n