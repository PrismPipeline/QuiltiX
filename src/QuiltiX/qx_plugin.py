import importlib.util
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Union

import pluggy

if TYPE_CHECKING:
    from QuiltiX import quiltix


# The environment variable that contains the paths to the plugins
PLUGINS_ENV_VAR = "QUILTIX_PLUGIN_PATHS"

# The name of the plugin file
PLUGIN_FILE_NAME = "plugin"  # .py

# Necessary function name by each plugin to implement and return a QuiltiXPlugin instance
PLUGIN_NAME_FUNCTION_NAME = "plugin_name"

# If a plugin decides it can be invalid (e.g. missing dependencies), it can implement this function
PLUGIN_VALID_FUNCTION_NAME = "is_valid"

logger = logging.getLogger(__name__)
hookspec = pluggy.HookspecMarker("QuiltiX")
hookimpl = pluggy.HookimplMarker("QuiltiX")

PathOrStr = Union[Path, str]


class QuiltiXPluginManager(pluggy.PluginManager):
    def load_plugins_from_dir(self, plugin_dir: PathOrStr):
        """
        Load all plugins from a directory. Each plugin is expected to have a `plugin.py` file in the root of the
        directory. The `plugin.py` file should contain a function named `plugin_id` that returns a QuiltiXPlugin
        instance.
        """
        # Check for the presence of plugin.py in the subfolder
        plugin_file = plugin_dir / "plugin.py"
        if not plugin_file.exists():
            logger.warning(f"Plugin file not found at {plugin_file}")
            return

        module_name = f"{str(plugin_dir)}.plugin"
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check for necessary presence of PLUGIN_NAME_FUNCTION_NAME function
        # and skip if it does not exist or does not return a string
        if hasattr(module, PLUGIN_NAME_FUNCTION_NAME):
            plugin_name_function = getattr(module, PLUGIN_NAME_FUNCTION_NAME)
            plugin_name: Any = plugin_name_function()
            if not isinstance(plugin_name, str):
                logger.warning(f"Plugin name {plugin_name} is not valid. Skipping plugin at {module.__file__}")
                return
        else:
            logger.warning(
                f"Found plugin at {module.__file__}, but i does not have a '{PLUGIN_NAME_FUNCTION_NAME}' function."
            )
            return

        # Check for presence of PLUGIN_VALID_FUNCTION_NAME function and skip if it returns False
        if hasattr(module, PLUGIN_VALID_FUNCTION_NAME):
            plugin_valid_function = getattr(module, PLUGIN_VALID_FUNCTION_NAME)
            if not plugin_valid_function():
                logger.warning(f"Plugin {plugin_name} is not valid. Skipping plugin at {module.__file__}")
                return

        try:
            self.register(module, plugin_name)
            logger.info(f"Registered plugin '{plugin_name} at {module.__file__}")
        except ValueError:
            logger.warning(f"Plugin with name '{plugin_name}' already registered. Skipping plugin at {module.__file__}")

    def load_plugins_from_environment_variable(self, environment_variable: str = PLUGINS_ENV_VAR):
        """
        Loop through an environment variable and load all plugins from the directories specified in the environment.
        """
        env_value: str = os.getenv(environment_variable, "")
        env_values: List[str] = [env_value for env_value in env_value.split(os.pathsep) if env_value]
        if not env_values:
            return

        plugin_root_dirs: List[Path] = [Path(env_value) for env_value in env_values if Path(env_value).is_dir()]
        for plugin_root_dir in plugin_root_dirs:
            self.load_plugins_from_dir(plugin_root_dir)


class QuiltixHookspecs:
    @hookspec
    def before_ui_init(self, editor: "quiltix.QuiltiXWindow"):
        """
        :param editor: The QuiltiX Window
        """

    @hookspec
    def after_ui_init(self, editor: "quiltix.QuiltiXWindow"):
        """
        :param editor: The QuiltiX Window
        """

    @hookspec
    def before_mx_import(self):
        """
        This allows any code to execute before MaterialX gets imported
        Useful for adjusting environment variables before MaterialX gets imported
        """

    @hookspec
    def after_mx_import(self):
        """
        This allows any code to execute after MaterialX gets imported
        """

    @hookspec
    def before_pxr_import(self):
        """
        This allows any code to execute before OpenUSD's pxr gets imported
        Useful for adjusting environment variables before pxr gets imported
        """

    @hookspec
    def after_pxr_import(self):
        """
        This allows any code to execute before OpenUSD's pxr gets imported
        """
