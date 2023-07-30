from examples.load_amd_wooden_flooring_mtlx import load_amd_wooden_flooring_mtlx
from examples.load_standard_surface_mtlx import load_standard_surface_mtlx


def test_load_standard_surface_mtlx(qtbot):
    load_standard_surface_mtlx()


def test_load_amd_wooden_flooring_mtlx(qtbot):
    load_amd_wooden_flooring_mtlx()
