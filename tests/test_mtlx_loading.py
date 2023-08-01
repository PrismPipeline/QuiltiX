from examples.load_amd_copper_mtlx import load_amd_copper_mtlx
from examples.load_standard_surface_mtlx import load_standard_surface_mtlx


def test_load_standard_surface_mtlx(qtbot):
    load_standard_surface_mtlx()


def test_load_amd_copper_mtlx(qtbot):
    load_amd_copper_mtlx()
