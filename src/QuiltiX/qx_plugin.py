import importlib.util
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, List, Union

import pluggy

if TYPE_CHECKING:
    from QuiltiX import quiltix


PLUGINS_ENV_VAR = "QUILTIX_PLUGIN_FOLDER"
PLUGIN_FILE_NAME = "plugin"
PLUGIN_ID_FUNCTION_NAME = "plugin_id"

logger = logging.getLogger(__name__)
hookspec = pluggy.HookspecMarker("QuiltiX")
hookimpl = pluggy.HookimplMarker("QuiltiX")

PathOrStr = Union[Path, str]


class QuiltiXPluginManager(pluggy.PluginManager):
    def load_plugins_from_dir(self, plugin_root_dir: PathOrStr):
        if not os.path.isdir(plugin_root_dir):
            raise FileNotFoundError(f"Plugin dir: '{plugin_root_dir}' does not exist.")

        plugin_root_dir = Path(plugin_root_dir)
        for dir in plugin_root_dir.iterdir():
            if not dir.is_dir():
                continue

            # Check for the presence of plugin.py in the subfolder
            plugin_file = dir / "plugin.py"
            if not plugin_file.is_file():
                continue

            module_name = f"{str(dir)}.plugin"
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Check for presence of PLUGIN_ID_FUNCTION_NAME function
            if hasattr(module, PLUGIN_ID_FUNCTION_NAME):
                plugin_id_function = getattr(module, PLUGIN_ID_FUNCTION_NAME)
                plugin_id_name = plugin_id_function()
                self.register(module, plugin_id_name)
                logger.info(f"Registered plugin '{plugin_id_name} at {module.__file__}")
            else:
                logger.warning(
                    f"Found plugin at {module.__file__}, but i does not have a '{PLUGIN_ID_FUNCTION_NAME}' function."
                )

    def load_plugins_from_environment_variable(self, environment_variable: str = PLUGINS_ENV_VAR):
        env_value: str = os.getenv(environment_variable, "")
        env_values: List[str] = [i for i in env_value.split(";") if i]
        if not env_values:
            return

        plugin_root_dirs: List[Path] = [Path(i) for i in env_values if Path(i).is_dir()]
        for plugin_root_dir in plugin_root_dirs:
            self.load_plugins_from_dir(plugin_root_dir)


class QuiltixHookspecs:
    @hookspec
    def after_ui_init(self, editor: "quiltix.QuiltiXWindow"):
        """
        :param editor: The QuiltiX Window
        """

    @hookspec
    def before_ui_init(self, editor: "quiltix.QuiltiXWindow"):
        """
        :param editor: The QuiltiX Window
        """

    @hookspec
    def before_mx_import(self):
        """
        This allows any code to execute before MaterialX gets imported
        """

    @hookspec
    def before_pxr_import(self):
        """
        This allows any code to execute before OpenUSD's pxr gets imported
        """
