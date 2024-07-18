import os
import sys
from contextlib import contextmanager

from qtpy.QtWidgets import QApplication  # type: ignore

from QuiltiX import quiltix


@contextmanager
def quiltix_instance(load_shaderball=True, load_default_graph=False):
    """Context manager starting QuiltiX and giving access to its object to execute examples.
    The context manager handles ui setup and teardown.

    Args:
        load_shaderball (bool, optional): Start QuiltiX with a Shaderball. Defaults to True.
        load_default_graph (bool, optional): Start QuiltiX with a default graph. Defaults to False.

    Yields:
        QuiltiXWindow: Instance of the QuiltiXWindow class.
    """

    if QApplication.instance() is None:
        app = QApplication(sys.argv)

    editor = quiltix.QuiltiXWindow(
        load_shaderball=load_shaderball,
        load_default_graph=load_default_graph
    )
    yield editor

    # The QApplication provided py pytest-qt does not need to be exited
    if not os.getenv("PYTEST_CURRENT_TEST", None):
        sys.exit(app.exec_())
