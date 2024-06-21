#
# Sample plug-in for QuiltiX which adds import, export, and preview functionality for MaterialX in JSON format
#    
import logging, os
from qtpy import QtCore # type: ignore
from qtpy.QtWidgets import (  # type: ignore
    QAction,
    QTextEdit )

logger = logging.getLogger(__name__)

try:
    import materialxjson.core as jsoncore
except ImportError:
    logger.error("materialxjson.core not found")

class QuiltiX_JSON_serializer():

    def __init__(self, editor, root):
        '''
        Initialize the JSON serializer.
        '''
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
        '''
        Set the indent for the JSON output.
        '''
        self.indent = indent

    def get_json_from_graph(self):
        '''
        Get the JSON for the given MaterialX document.
        '''
        doc = self.editor.qx_node_graph.get_current_mx_graph_doc()
        if doc:
            exporter = jsoncore.MaterialXJson()
            json_result = exporter.documentToJSON(doc)
            return json_result 
        return None

    def show_json_triggered(self):
        '''
        Show the current USD Stage.
        '''
        json_result = self.get_json_from_graph() 

        # Write JSON UI text box
        if json_result:
            text = jsoncore.Util.jsonToJSONString(json_result, self.indent)
            self.show_text_box(text, 'JSON Representation')

    def export_json_triggered(self):
        '''
        Export the current graph to a JSON file.
        '''
        start_path = self.editor.mx_selection_path
        if not start_path:
            start_path = self.editor.geometry_selection_path

        if not start_path:
            start_path = os.path.join(self.root, "resources", "materials")

        path = self.editor.request_filepath(
            title="Save JSON file", start_path=start_path, file_filter="JSON files (*.json)", mode="save",
        )

        if not path:
            return

        json_result = self.get_json_from_graph() 

        # Write JSON to file
        if json_result:
            with open(path, 'w') as outfile:
                jsoncore.Util.writeJson(json_result, path, 2)
                logger.info('Wrote JSON file: ' + path)

        self.editor.set_current_filepath(path)

    def import_json_triggered(self):
        '''
        Import a JSON file into the current graph.
        '''
        start_path = self.editor.mx_selection_path
        if not start_path:
            start_path = self.editor.geometry_selection_path

        if not start_path:
            start_path = os.path.join(self.root, "resources", "materials")

        path = self.editor.request_filepath(
            title="Load JSON file", start_path=start_path, file_filter="JSON files (*.json)", mode="open",
        )

        if not os.path.exists(path):
            logger.error('Cannot find input file: ' + path)
            return

        doc = jsoncore.Util.jsonFileToXml(path) 
        if doc:
            logger.info('Loaded JSON file: ' + path)
            self.editor.mx_selection_path = path
            self.editor.qx_node_graph.load_graph_from_mx_doc(doc)
            self.editor.qx_node_graph.mx_file_loaded.emit(path)

    # Helper functions
    def show_text_box(self, text, title=""):
        '''
        Show a text box with the given text.
        '''
        te_text = QTextEdit()
        te_text.setText(text)
        te_text.setReadOnly(True)
        te_text.setParent(self.editor, QtCore.Qt.Window)
        te_text.setWindowTitle(title)
        te_text.resize(1000, 800)
        te_text.show()

def install_plugin(editor, root, result):
    '''
    Plugin entry point.
    '''
    if not jsoncore:
        logger.error("MaterialX JSON plugin not installed")
        return [None, None]
    
    plugin = QuiltiX_JSON_serializer(editor, root)

    result.plugin = plugin
    result.id = "MaterialX JSON Serializer"
