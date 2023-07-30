import pytest
import helpers


@pytest.fixture
def quiltix_instance(qtbot):
    """
    Args:
        load_shaderball (bool, optional): Start Quiltix with a Shaderball. Defaults to True.
        load_default_graph (bool, optional): Start Quiltix with a default graph. Defaults to False.

    Yields:
        QuiltiXWindow: Instance of the QuiltiXWindow class.
    """
    with helpers.quiltix_instance() as editor:
        yield editor
