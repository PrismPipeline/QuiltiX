from NodeGraphQt.custom_widgets.properties_bin import custom_widget_color_picker, custom_widget_file_paths
from qtpy.QtGui import QColor # type: ignore
from qtpy.QtWidgets import QColorDialog # type: ignore


class QxPropFilePath(custom_widget_file_paths.PropFilePath):
    """
    Displays a node property as a "QFileDialog" save widget in the
    PropertiesBin.
    """

    def _on_value_change(self, value=None):
        if value is None:
            value = self._ledit.text()

        self.set_file_directory(value)
        self.value_changed.emit(self.toolTip(), value)


class QxPropColorPickerRGBFloat(custom_widget_color_picker.PropColorPickerRGB):
    """
    Float Color picker widget for a node property.
    """

    def _on_select_color(self):
        if self._realtime_update:
            current_color = QColor(*[c*255 for c in self.get_value()])
            self.color_dialog = QColorDialog(current_color, self)
            self.color_dialog.currentColorChanged.connect(self._on_current_color_changed)
            self.color_dialog.show()
        else:
            current_color = QColor(*self.get_value())
            color = QColorDialog.getColor(current_color, self)
            if color.isValid():
                self.set_value([round(c/255, 6) for c in color.getRgb()])

    def _on_current_color_changed(self, color):
        if color.isValid():
            self.set_value([round(c/255, 6) for c in color.getRgb()])

    def _update_color(self):
        c = [int(max(min(i*255, 255), 0)) for i in self._color]
        hex_color = '#{0:02x}{1:02x}{2:02x}'.format(*c)
        self._button.setStyleSheet(
            '''
            QPushButton {{background-color: rgba({0}, {1}, {2}, 255);}}
            QPushButton::hover {{background-color: rgba({0}, {1}, {2}, 200);}}
            '''.format(*c)
        )
        self._button.setToolTip(
            'rgb: {}\nhex: {}'.format(self._color[:3], hex_color)
        )


class QxPropColorPickerRGBAFloat(custom_widget_color_picker.PropColorPickerRGBA):
    """
    Float Color picker widget for a node property.
    """

    def _on_select_color(self):
        if self._realtime_update:
            current_color = QColor(*[c*255 for c in self.get_value()])
            self.color_dialog = QColorDialog(current_color, self)
            self.color_dialog.currentColorChanged.connect(self._on_current_color_changed)
            self.color_dialog.show()
        else:
            current_color = QColor(*self.get_value())
            color = QColorDialog.getColor(current_color, self)
            if color.isValid():
                self.set_value([round(c/255, 6) for c in color.getRgb()])

    def _on_current_color_changed(self, color):
        if color.isValid():
            self.set_value([round(c/255, 6) for c in color.getRgb()])

    def _update_color(self):
        c = [int(max(min(i*255, 255), 0)) for i in self._color]
        hex_color = '#{0:02x}{1:02x}{2:02x}'.format(*c)
        self._button.setStyleSheet(
            '''
            QPushButton {{background-color: rgba({0}, {1}, {2}, 255);}}
            QPushButton::hover {{background-color: rgba({0}, {1}, {2}, 200);}}
            '''.format(*c)
        )
        self._button.setToolTip(
            'rgb: {}\nhex: {}'.format(self._color[:3], hex_color)
        )