import NodeGraphQt


class QxTabSearchWidget(
    NodeGraphQt.widgets.viewer.TabSearchMenuWidget
):
    def __init__(self, node_dict=None):
        self.port_to_connect = None
        super(QxTabSearchWidget, self).__init__()

        # override TabSearchMenuWidget stylesheet
        self._menu_stylesheet = """
            QMenu, QMenu::item {
                color: #ffffff;
                background-color: #111111;
            }

            QMenu::item:selected, QMenu::item:pressed {
                background-color: #333333;
            }
        """
        self.setStyleSheet(self._menu_stylesheet)

        # override text color of line edit in search menu
        self._line_edit_stylesheet = self.line_edit.styleSheet() + """
        QLineEdit {
            color: #ffffff;
        }
        """
        self.line_edit.setStyleSheet(self._line_edit_stylesheet)

    def _on_text_changed(self, text):
        self.setHidden(True)
        super(QxTabSearchWidget, self)._on_text_changed(text)
        self.setHidden(False)

    def _close(self):
        self.port_to_connect = None
        super(QxTabSearchWidget, self)._close()