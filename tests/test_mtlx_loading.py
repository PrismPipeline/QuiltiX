from examples.load_amd_wooden_flooring_mtlx import load_amd_wooden_flooring_mtlx
from examples.load_simple_mtlx import load_simple_mtlx


def test_load_simple_mtlx(qtbot):
    load_simple_mtlx()


def test_load_amd_wooden_flooring_mtlx(qtbot):
    load_amd_wooden_flooring_mtlx()
