# Sample plug-in for QuiltiX which adds import, export, and preview functionality for MaterialX in JSON format

import logging
import os

# Optional syntax highlighting if pygments is installed
have_highliting = True
try:
    from pygments import highlight
    from pygments.lexers import JsonLexer
    from pygments.formatters import HtmlFormatter
except ImportError:
    have_highliting = False

from typing import TYPE_CHECKING

from qtpy import QtCore  # type: ignore
from qtpy.QtWidgets import (  # type: ignore
    QAction,
    QTextEdit,
)
from QuiltiX import constants, qx_plugin

logger = logging.getLogger(__name__)
has_materialxjsoncore = True

try:
    import materialxjson.core as jsoncore
except ImportError:
    has_materialxjsoncore = False
    logger.error("materialxjson.core module not found")

if TYPE_CHECKING:
    from QuiltiX import quiltix


class JsonHighlighter:
    def __init__(self):
        self.lexer = JsonLexer()
        # We don't add line numbers since this get's copied with
        # copy-paste.
        self.formatter = HtmlFormatter(linenos=False, style='github-dark')

    def highlight(self, text):
        highlighted_html = highlight(text, self.lexer, self.formatter)
        styles = (
            f"<style>"
            f"{self.formatter.get_style_defs('.highlight')}"
            f"pre {{ line-height: 1.0; margin: 0; }}"
            f"</style>"
        )
        full_html = f"<html><head>{styles}</head><body>{highlighted_html}</body></html>"     
        return full_html

class QuiltiX_JSON_serializer:
    def __init__(self, editor, root):
        """
        Initialize the JSON serializer.
        """
        self.editor = editor
        self.root = root
        self.indent = 4

        # Add JSON menu to the file menu
        # ----------------------------------------
        editor.file_menu.addSeparator()
        gltfMenu = editor.file_menu.addMenu("JSON")

        # Export JSON item
        export_json = QAction("Save JSON...", editor)
        export_json.triggered.connect(self.export_json_triggered)
        gltfMenu.addAction(export_json)

        # Import JSON item
        import_json = QAction("Load JSON...", editor)
        import_json.triggered.connect(self.import_json_triggered)
        gltfMenu.addAction(import_json)

        # Show JSON text. Does most of export, except does not write to file
        show_json_text = QAction("Show as JSON...", editor)
        show_json_text.triggered.connect(self.show_json_triggered)
        gltfMenu.addAction(show_json_text)

    def set_indent(self, indent):
        """
        Set the indent for the JSON output.
        """
        self.indent = indent

    def get_json_from_graph(self):
        """
        Get the JSON for the given MaterialX document.
        """
        doc = self.editor.qx_node_graph.get_current_mx_graph_doc()
        if doc:
            exporter = jsoncore.MaterialXJson()
            json_result = exporter.documentToJSON(doc)
            return json_result
        return None

    def show_json_triggered(self):
        """
        Show the JSON for the current MaterialX document.
        """
        json_result = self.get_json_from_graph()

        # Write JSON UI text box
        if json_result:
            text = jsoncore.Util.jsonToJSONString(json_result, self.indent)
            self.show_text_box(text, "JSON Representation")

    def export_json_triggered(self, editor):
        """
        Export the current graph to a JSON file.
        """
        start_path = self.editor.mx_selection_path
        if not start_path:
            start_path = self.editor.geometry_selection_path

        if not start_path:
            start_path = os.path.join(self.root, "resources", "materials")

        path = self.editor.request_filepath(
            title="Save JSON file",
            start_path=start_path,
            file_filter="JSON files (*.json)",
            mode="save",
        )

        if not path:
            return

        json_result = self.get_json_from_graph()

        # Write JSON to file
        if json_result:
            with open(path, "w"):
                jsoncore.Util.writeJson(json_result, path, 2)
                logger.info("Wrote JSON file: " + path)

        self.editor.set_current_filepath(path)

    def import_json_triggered(self, editor):
        """
        Import a JSON file into the current graph.
        """
        start_path = self.editor.mx_selection_path
        if not start_path:
            start_path = self.editor.geometry_selection_path

        if not start_path:
            start_path = os.path.join(self.root, "resources", "materials")

        path = self.editor.request_filepath(
            title="Load JSON file",
            start_path=start_path,
            file_filter="JSON files (*.json)",
            mode="open",
        )
        if not path:
            return

        if not os.path.exists(path):
            logger.error("Cannot find input file: " + path)
            return

        doc = jsoncore.Util.jsonFileToXml(path)
        if doc:
            logger.info("Loaded JSON file: " + path)
            self.editor.mx_selection_path = path
            self.editor.qx_node_graph.load_graph_from_mx_doc(doc)
            self.editor.qx_node_graph.mx_file_loaded.emit(path)

    # Helper functions
    def show_text_box(self, text, title=""):
        """
        Show a text box with the given text.
        """
        te_text = QTextEdit()
        te_text.setReadOnly(True)
        te_text.setParent(self.editor, QtCore.Qt.Window)
        te_text.setWindowTitle(title)
        te_text.resize(1000, 800)

        if have_highliting:
            jsonHighlighter = JsonHighlighter()
            highlighted_html = jsonHighlighter.highlight(text)
            te_text.setHtml(highlighted_html)
        else:
            te_text.setPlainText(text)        

        te_text.show()


@qx_plugin.hookimpl
def after_ui_init(editor: "quiltix.QuiltiXWindow"):
    editor.json_serializer = QuiltiX_JSON_serializer(editor, constants.ROOT)


def plugin_name() -> str:
    return "MaterialX JSON Serializer"


def is_valid() -> bool:
    return has_materialxjsoncore