import importlib.util, os, logging

logger = logging.getLogger(__name__)

class QuiltiXPlugin():
    def __init__(self):
        self.id = ""
        self.plugin = None

class QuiltiXPluginManager():
    def __init__(self, editor, root):
        self.editor = editor
        self.root = root
        self.plugins = []

    def install_plugins(self):
        self.plugins = []
        plugin_roots = [os.path.join(self.root, "plugins"), os.getenv("QUILTIX_PLUGIN_FOLDER", "")]
        for plugin_folder in plugin_roots:
            if os.path.exists(plugin_folder):
                absolute_plugin_folder = os.path.abspath(plugin_folder)
                logger.debug(f"Loading plugin from {absolute_plugin_folder}...")                
                self.install_plugins_from_folder(plugin_folder)

    def install_plugins_from_folder(self, plugin_folder):
        if not os.path.isdir(plugin_folder):
            logger.warning(f"Plugin folder {plugin_folder} not found.")
            return
        
        # Get the list of all subfolders in the plugin_folder
        for entry in os.listdir(plugin_folder):
            entry_path = os.path.join(plugin_folder, entry)

            if os.path.isdir(entry_path):
                # Check for the presence of plugin.py in the subfolder
                plugin_file = os.path.join(entry_path, 'plugin.py')
                if os.path.isfile(plugin_file):
                    module_name = f"{entry}.plugin"

                    # Dynamically import the module
                    spec = importlib.util.spec_from_file_location(module_name, plugin_file)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Call module install_plugin function if it exists
                    if hasattr(module, "install_plugin"):
                        pluginInfo = QuiltiXPlugin()
                        module.install_plugin(self.editor, self.root, pluginInfo)
                        if pluginInfo.id and pluginInfo.plugin:
                            pluginExists = None
                            for installed_plugin in self.plugins:
                                if installed_plugin.id == pluginInfo.id:
                                    pluginExists = installed_plugin
                                    break   
                            if pluginExists:
                                logger.warning(f"Plugin with id {pluginInfo.id} already installed.")
                            else:
                                self.plugins.append(pluginInfo)
                                logger.debug(f"Installed plugin {pluginInfo.id} from {plugin_file}.")
                    else:
                        logger.warning(f"No installPlugin function found in {plugin_file}.")    