from examples.create_all_available_nodes import create_all_available_nodes
from examples.create_standard_surface import create_standard_surface


def test_create_all_available_nodes(qtbot):
    create_all_available_nodes()


def test_create_standard_surface(qtbot):
    create_standard_surface()
