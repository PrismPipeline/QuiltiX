import os

from QuiltiX import constants
from tests import helpers


def load_standard_surface_mtlx():
    with helpers.quiltix_instance() as editor:
        mx_file = os.path.join(constants.ROOT, "resources", "materials", "standard_surface.mtlx")
        editor.qx_node_graph.load_graph_from_mx_file(mx_file)


if __name__ == "__main__":
    load_standard_surface_mtlx()
