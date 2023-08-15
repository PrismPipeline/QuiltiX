from Qt.QtCore import Qt # type: ignore
from Qt.QtWidgets import QDoubleSpinBox, QLineEdit, QFormLayout, QWidget, QCheckBox, QSpinBox  # type: ignore

from pxr.Usdviewq.stageView import StageView, UsdImagingGL

class RenderSettingsWidget(QWidget):

    def __init__(self, stage_view, window_title="Render Settings"):
        super(RenderSettingsWidget, self).__init__()
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.stage_view = stage_view
        self.layout = QFormLayout(self)

    def on_renderer_changed(self):
        self._clear_widgets()
        self._populate_widgets()

    def _clear_widgets(self):
        for i in reversed(range(self.layout.count())):
            widgetToRemove = self.layout.itemAt(i).widget()
            self.layout.removeWidget(widgetToRemove)
            widgetToRemove.setParent(None)

    def _populate_widgets(self):
        settings = self.stage_view.GetRendererSettingsList()

        for setting in settings:
            if setting.type == UsdImagingGL.RendererSettingType.FLAG:
                checkBox = QCheckBox(self)
                checkBox.setChecked(self.stage_view.GetRendererSetting(setting.key))
                checkBox.key = str(setting.key)
                checkBox.defValue = setting.defValue
                checkBox.toggled.connect(lambda v, setting=setting: self.stage_view.SetRendererSetting(setting.key, v))
                self.layout.addRow(setting.name, checkBox)
            elif setting.type == UsdImagingGL.RendererSettingType.INT:
                spinBox = QSpinBox(self)
                spinBox.setMinimum(-2 ** 31)
                spinBox.setMaximum(2 ** 31 - 1)
                spinBox.setValue(self.stage_view.GetRendererSetting(setting.key))
                spinBox.key = str(setting.key)
                spinBox.defValue = setting.defValue
                spinBox.valueChanged.connect(lambda v, setting=setting: self.stage_view.SetRendererSetting(setting.key, v))
                self.layout.addRow(setting.name, spinBox)
            elif setting.type == UsdImagingGL.RendererSettingType.FLOAT:
                spinBox = QDoubleSpinBox(self)
                spinBox.setDecimals(10)
                spinBox.setMinimum(-2 ** 31)
                spinBox.setMaximum(2 ** 31 - 1)
                spinBox.setValue(self.stage_view.GetRendererSetting(setting.key))
                spinBox.key = str(setting.key)
                spinBox.defValue = setting.defValue
                spinBox.valueChanged.connect(lambda v, setting=setting: self.stage_view.SetRendererSetting(setting.key, v))
                self.layout.addRow(setting.name, spinBox)
            elif setting.type == UsdImagingGL.RendererSettingType.STRING:
                lineEdit = QLineEdit(self)
                lineEdit.setText(self.stage_view.GetRendererSetting(setting.key))
                lineEdit.key = str(setting.key)
                lineEdit.defValue = setting.defValue
                lineEdit.textChanged.connect(lambda v, setting=setting: self.stage_view.SetRendererSetting(setting.key, v))
                self.layout.addRow(setting.name, lineEdit)
