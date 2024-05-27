import logging
from collections import defaultdict

from NodeGraphQt.constants import NodePropWidgetEnum
from NodeGraphQt.custom_widgets.properties_bin import (
    node_property_widgets,
    custom_widget_slider,
)
from NodeGraphQt.custom_widgets.properties_bin.node_property_factory import NodePropertyWidgetFactory
from NodeGraphQt.custom_widgets.properties_bin.prop_widgets_base import PropLineEdit
from qtpy.QtCore import QSize, Qt, Signal, QEvent  # type: ignore
from qtpy.QtGui import QMouseEvent  # type: ignore
from qtpy.QtWidgets import (  # type: ignore
    QHBoxLayout,
    QLabel,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
)

from QuiltiX import constants
from QuiltiX.qx_node_property_widgets import QxPropColorPickerRGBAFloat, QxPropColorPickerRGBFloat, QxPropFilePath

logger = logging.getLogger(__name__)


class NodePropWidget(node_property_widgets.NodePropWidget):
    """
    Node properties widget for display a Node object.

    Args:
        parent (QtWidgets.QWidget): parent object.
        node (NodeGraphQt.BaseNode): node.
    """

    #: signal (node_id, prop_name, prop_value)
    property_changed = Signal(str, str, object)
    property_closed = Signal(str)

    def __init__(self, parent=None, node=None):
        super(node_property_widgets.NodePropWidget, self).__init__(parent)
        self.__node_id = node.id
        self.__tab_windows = {}
        self.__tab = QTabWidget()

        # custom start - disable close button
        # close_btn = QtWidgets.QPushButton()
        # close_btn.setIcon(QtGui.QIcon(
        #     self.style().standardPixmap(QtWidgets.QStyle.SP_DialogCancelButton)
        # ))
        # close_btn.setMaximumWidth(40)
        # close_btn.setToolTip('close property')
        # close_btn.clicked.connect(self._on_close)
        # custom end

        self.name_wgt = PropLineEdit()
        self.name_wgt.setToolTip('name')
        self.name_wgt.set_value(node.name())
        self.name_wgt.value_changed.connect(self._on_property_changed)

        # custom start - disable type widget button
        # self.type_wgt = QtWidgets.QLabel(node.type_)
        # self.type_wgt.setAlignment(QtCore.Qt.AlignRight)
        # self.type_wgt.setToolTip('type_')
        # font = self.type_wgt.font()
        # font.setPointSize(10)
        # self.type_wgt.setFont(font)
        # custom end

        name_layout = QHBoxLayout()
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.addWidget(QLabel('name'))
        name_layout.addWidget(self.name_wgt)
        # custom start - disable adding of close button
        # name_layout.addWidget(close_btn)
        # custom end
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.addLayout(name_layout)
        # custom start - disable adding of tabs and type widgets
        # layout.addWidget(self.__tab)
        # layout.addWidget(self.type_wgt)
        # custom end
        self._read_node(node)

        # custom start - styled/transparent background
        self.setAttribute(Qt.WA_StyledBackground, True)
        # custom end

    def _read_node(self, node):
        """
        Populate widget from a node.

        Args:
            node (NodeGraphQt.BaseNode): node class.
        """
        model = node.model
        graph_model = node.graph.model

        common_props = graph_model.get_node_common_properties(node.type_)

        # sort tabs and properties.
        tab_mapping = defaultdict(list)
        for prop_name, prop_val in model.custom_properties.items():
            tab_name = model.get_tab_name(prop_name)
            tab_mapping[tab_name].append((prop_name, prop_val))

        # add tabs.
        for tab in sorted(tab_mapping.keys()):
            if tab != 'Node':
                self.add_tab(tab)

        # property widget factory.
        widget_factory = NodePropertyWidgetFactory()
        widget_factory._widget_mapping[NodePropWidgetEnum.FILE_OPEN.value] = QxPropFilePath
        realtime_update = True
        widget_factory._widget_mapping[
            NodePropWidgetEnum.DOUBLE_SLIDER.value
        ] = lambda parent=None, decimals=constants.VALUE_DECIMALS: custom_widget_slider.PropDoubleSlider(
            parent=parent, decimals=decimals, realtime_update=realtime_update
        )
        widget_factory._widget_mapping[
            NodePropWidgetEnum.SLIDER.value
        ] = lambda parent=None: custom_widget_slider.PropSlider(
            parent=parent, realtime_update=realtime_update
        )
        widget_factory._widget_mapping[
            NodePropWidgetEnum.COLOR_PICKER.value
        ] = lambda parent=None: QxPropColorPickerRGBFloat(
            parent=parent, realtime_update=realtime_update
        )
        widget_factory._widget_mapping[
            NodePropWidgetEnum.COLOR4_PICKER.value
        ] = lambda parent=None: QxPropColorPickerRGBAFloat(
            parent=parent, realtime_update=realtime_update
        )

        # populate tab properties.
        for tab in sorted(tab_mapping.keys()):
            prop_window = self.__tab_windows[tab]
            for prop_name, value in tab_mapping[tab]:
                wid_type = node.get_widget_type(prop_name)
                if wid_type == 0:
                    continue

                widget = widget_factory.get_widget(wid_type)
                if prop_name in common_props.keys():
                    if 'items' in common_props[prop_name].keys():
                        widget.set_items(common_props[prop_name]['items'])
                    if 'range' in common_props[prop_name].keys():
                        prop_range = common_props[prop_name]['range']
                        widget.set_min(prop_range[0])
                        widget.set_max(prop_range[1])
                    else:
                        if hasattr(widget, "_spinbox"):
                            widget._spinbox.setMaximum(constants.MAXIMUM_FLOAT)
                            widget._slider.setMaximum(10)

                if hasattr(widget, "_slider"):
                    widget._slider.origMousePressEvent = widget._slider.mousePressEvent
                    widget._slider.mousePressEvent = lambda e, w=widget: self.slider_drag_patch(w, e)

                # try:
                if type(value) == str and ", " in value:
                    value = (v.strip() for v in value.split(","))

                
                if type(value) in [tuple, list] and type(widget.get_value()) in [tuple, list]:
                    if len(value) < len(widget.get_value()):
                        value = widget.get_value()
                elif type(value) != type(widget.get_value()):
                    value = widget.get_value()                    

                prop_window.add_widget(prop_name, widget, value,
                                       prop_name.replace('_', ' '))
                # except:
                #     logger.warning(f"failed to add propterty widget: {prop_name}", value)
                #     continue

                widget.value_changed.connect(self._on_property_changed)

                # custom start - custom label
                label = prop_window._PropertiesContainer__layout.itemAtPosition(
                    prop_window._PropertiesContainer__layout.rowCount() - 1, 0
                ).widget()
                if node.type_ in ["Other.QxGroupNode", "Inputs.QxPortInputNode", "Outputs.QxPortOutputNode"]:
                    labelText = prop_name
                else:
                    labelText = node.get_mx_input_name_from_property_name(prop_name).replace("_", " ")
                    mx_input = node.current_mx_def.getActiveInput(prop_name)
                    hasGeomProp = mx_input and mx_input.getDefaultGeomProp()
                    if hasGeomProp:
                        widget.setDisabled(True)
                        label.setDisabled(True)

                label.setText(labelText.capitalize() + ": ")

                # custom start - disable widget if the widget's corresponding input is wired up
                if prop_name in node.inputs():
                    if node.inputs()[prop_name].connected_ports():
                        widget.setDisabled(True)
                        label.setDisabled(True)
                        # TODO: roll over to NodeGraphQt
                        if hasattr(widget, "_spinbox"):
                            widget._slider.setDisabled(True)
                            widget._spinbox.setDisabled(True)
                # custom end - disable widget

        self.layout().itemAt(0).itemAt(0).widget().setText(getattr(node, "__label__", node.__identifier__))
        # custom end - custom label

        # custom start - disable node tab
        # self.add_tab('Node')
        # default_props = ['color', 'text_color', 'disabled', 'id']
        # prop_window = self.__tab_windows['Node']
        # for prop_name in default_props:
        #     wid_type = model.get_widget_type(prop_name)
        #     widget = widget_factory.get_widget(wid_type)
        #     prop_window.add_widget(prop_name,
        #                            widget,
        #                            model.get_property(prop_name),
        #                            prop_name.replace('_', ' '))

        #     widget.value_changed.connect(self._on_property_changed)

        # self.type_wgt.setText(model.get_property('type_'))
        # custom end

    def update_widget_availability(self, node):
        # TODO when current node gets new input, refresh if if widgets should be disabled or not
        pass

    def slider_drag_patch(self, widget, event):
        custEvent = QMouseEvent(
            QEvent.MouseButtonPress,
            event.pos(),
            Qt.MidButton,
            Qt.MidButton,
            Qt.NoModifier,
        )
        widget._slider.origMousePressEvent(custEvent)

    def add_tab(self, name):
        """
        add a new tab.

        Args:
            name (str): tab name.

        Returns:
            PropWindow: tab child widget.
        """
        if name in self.__tab_windows.keys():
            raise AssertionError("Tab name {} already taken!".format(name))

        #  custom start - add properties to widget layout instead of in tab
        self.__tab_windows[name] = node_property_widgets._PropertiesContainer(self)
        self.layout().addWidget(self.__tab_windows[name])
        #  custom end

        return self.__tab_windows[name]


class PropertiesBinWidget(node_property_widgets.PropertiesBinWidget):
    def __init__(self, parent=None, root_node_graph=None):
        # custom start - call original init and then hide unnecessary widgets and connect custom signals
        super(PropertiesBinWidget, self).__init__(parent, root_node_graph)
        self.layout().itemAt(0).itemAt(0).widget().setHidden(True)
        self.layout().itemAt(0).itemAt(2).widget().setHidden(True)
        self.layout().itemAt(0).itemAt(3).widget().setHidden(True)
        self.layout().setContentsMargins(0, 0, 0, 0)
        lo = self.layout().takeAt(0)
        lo.setParent(None)
        lo.deleteLater()
        root_node_graph.node_double_clicked.disconnect()
        self._limit.setValue(1)
        self.change_node_graph(root_node_graph)

        root_node_graph.node_graph_changed.connect(self.change_node_graph)
        root_node_graph.widget.currentChanged.connect(self.on_tab_changed)
        # custom end

    def on_tab_changed(self):
        widget = self.node_graph.get_root_graph().widget.currentWidget()
        if widget.__class__.__name__ == "QxNodeGraphViewer":
            graph = widget.graph
        else:
            graph = widget._graph

        self.change_node_graph(graph)

    # custom start
    def change_node_graph(self, node_graph):
        node_graph.node_selected.connect(self.add_node)
        node_graph.node_selection_changed.connect(self.on_node_selection_changed)
        node_graph.node_created.connect(self._on_node_created)
        node_graph.mx_file_loaded.connect(self._on_file_loaded)
        self.node_graph = node_graph
        self.add_selected_node()
        # TODO why doesnt this work for subgraphs?
        # node_graph.node_double_clicked.disconnect()
    # custom end

    # custom start - set default size for PropertiesBinWidget
    def sizeHint(self):
        return QSize(500, 400)
    # custom end

    # custom start - allow clearing widget on deselection
    def on_node_selection_changed(self, sel_nodes, unsel_nodes):
        self.add_selected_node()
    # custom end

    def add_node(self, node):
        """
        Add node to the properties bin.

        Args:
            node (NodeGraphQt.NodeObject): node object.
        """
        if self.limit() == 0 or self._lock:
            return

        rows = self._prop_list.rowCount()
        if rows >= self.limit():
            self._prop_list.removeRow(rows - 1)

        itm_find = self._prop_list.findItems(node.id, Qt.MatchExactly)
        if itm_find:
            self._prop_list.removeRow(itm_find[0].row())

        self._prop_list.insertRow(0)
        # custom start - use custom qx_node_property.NodePropWidget
        prop_widget = NodePropWidget(node=node)
        # custom end
        prop_widget.property_changed.connect(self.__on_property_widget_changed)
        prop_widget.property_closed.connect(self.__on_prop_close)
        self._prop_list.setCellWidget(0, 0, prop_widget)

        item = QTableWidgetItem(node.id)
        self._prop_list.setItem(0, 0, item)
        self._prop_list.selectRow(0)

    # custom start - show node properties when node gets created
    def _on_node_created(self, node):
        if self.node_graph.get_root_graph()._block_save:
            return

        self.add_node(node)
    # custom end

    # custom start - show node properties of selected node after file was loaded
    def _on_file_loaded(self, filepath):
        self.add_selected_node()
    # custom end

    # custom start - show node properties of selected node
    def add_selected_node(self):
        nodes = self.node_graph.selected_nodes()
        if nodes:
            self.add_node(nodes[0])
        else:
            self.clear_bin()
    # custom end
