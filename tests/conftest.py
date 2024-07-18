import pytest
import helpers
from pathlib import Path
from QuiltiX.constants import ROOT


@pytest.fixture
def quiltix_instance(qtbot):
    """
    Args:
        load_shaderball (bool, optional): Start QuiltiX with a Shaderball. Defaults to True.
        load_default_graph (bool, optional): Start QuiltiX with a default graph. Defaults to False.

    Yields:
        QuiltiXWindow: Instance of the QuiltiXWindow class.
    """
    with helpers.quiltix_instance() as editor:
        yield editor


@pytest.fixture
def materialxjson_plugin():
    import os

    os.environ["QUILTIX_PLUGIN_PATHS"] = (
        str((Path(ROOT).parent.parent / "sample_plugins/materialxjson")) + os.pathsep + os.environ.get("QUILTIX_PLUGIN_PATHS", "")
    )
