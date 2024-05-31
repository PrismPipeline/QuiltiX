from qtpy import QtWidgets, QtCore  # type: ignore
from QuiltiX.constants import VALUE_DECIMALS

from pxr.Usdviewq.stageView import UsdImagingGL  # type: ignore

# Inherit from _PropertiesList so the layouts & styling are the same
class RenderSettingsWidget(QtWidgets.QWidget):
    def __init__(self, stage_view, window_title="Render Settings"):
        super(RenderSettingsWidget, self).__init__()
        self.stage_view = stage_view

        # layout_root > scroll_area > scroll_area_main_widget > scroll_area_main_layout > grid_layout
        self.layout_root = QtWidgets.QHBoxLayout(self)
        self.scroll_area = QtWidgets.QScrollArea()
        self.layout_root.addWidget(self.scroll_area)
        self.scroll_area_main_widget = QtWidgets.QWidget()
        self.scroll_area.setWidget(self.scroll_area_main_widget)
        self.scroll_area_main_layout = QtWidgets.QVBoxLayout()
        self.scroll_area_main_widget.setLayout(self.scroll_area_main_layout)
        self.grid_layout = QtWidgets.QGridLayout()
        self.scroll_area_main_layout.addLayout(self.grid_layout)

        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll_area.setWidgetResizable(True)

        self.scroll_area_main_layout.setAlignment(QtCore.Qt.AlignTop)

        # TODO enable both columns to be resized simultaneously
        self.grid_layout.setSpacing(6)

        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
    
    def sizeHint(self):
        return QtCore.QSize(250, 250)

    def on_renderer_changed(self):
        self._clear_widgets()
        self._populate_widgets()

    def _clear_widgets(self):
        for i in reversed(range(self.grid_layout.count())):
            item_to_remove = self.grid_layout.itemAt(i)
            if item_to_remove:
                widget_to_remove = item_to_remove.widget()
                if widget_to_remove:
                    self.grid_layout.removeWidget(widget_to_remove)
                    widget_to_remove.deleteLater()

    def _populate_widgets(self):
        settings = self.stage_view.GetRendererSettingsList()
        label_flags = QtCore.Qt.AlignCenter | QtCore.Qt.AlignRight

        for row, setting in enumerate(settings):
            label_widget = QtWidgets.QLabel(f"{str(setting.key)}: ")
            self.grid_layout.addWidget(label_widget, row, 0, label_flags)
            
            value_widget = self._create_value_widget(setting)
            self.grid_layout.addWidget(value_widget, row, 1)

    def _create_value_widget(self, renderer_setting):
        value = self.stage_view.GetRendererSetting(renderer_setting.key)

        if renderer_setting.type == UsdImagingGL.RendererSettingType.FLAG:
            value_widget = QtWidgets.QCheckBox()

            value_widget.setChecked(value)

            value_widget.toggled.connect(lambda v, setting=renderer_setting:
                self.stage_view.SetRendererSetting(renderer_setting.key, v))

        elif renderer_setting.type == UsdImagingGL.RendererSettingType.INT:
            value_widget = QtWidgets.QSpinBox()
            value_widget.wheelEvent = lambda _: None

            value_widget.setMinimum(-(2**31))
            value_widget.setMaximum(2**31 - 1)

            value_widget.setValue(self.stage_view.GetRendererSetting(renderer_setting.key))

            value_widget.valueChanged.connect(
                lambda v, setting=renderer_setting: self.stage_view.SetRendererSetting(renderer_setting.key, v)
            )

        elif renderer_setting.type == UsdImagingGL.RendererSettingType.FLOAT:
            value_widget = QtWidgets.QDoubleSpinBox()
            value_widget.wheelEvent = lambda _: None

            value_widget.setDecimals(VALUE_DECIMALS)
            value_widget.setMinimum(-(2**31))
            value_widget.setMaximum(2**31 - 1)

            value_widget.setValue(self.stage_view.GetRendererSetting(renderer_setting.key))

            value_widget.valueChanged.connect(
                lambda v, setting=renderer_setting: self.stage_view.SetRendererSetting(renderer_setting.key, v)
            )

        elif renderer_setting.type == UsdImagingGL.RendererSettingType.STRING:
            value_widget = QtWidgets.QLineEdit()

            value_widget.setText(self.stage_view.GetRendererSetting(renderer_setting.key))

            value_widget.textChanged.connect(
                lambda v, setting=renderer_setting: self.stage_view.SetRendererSetting(renderer_setting.key, v)
            )

        return value_widget
