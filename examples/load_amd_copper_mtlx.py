import os

from QuiltiX import constants
from tests import helpers


def load_amd_copper_mtlx():
    with helpers.quiltix_instance() as editor:
        mx_file = os.path.join(
            constants.ROOT,
            "resources",
            "materials",
            "Mahogany_Chevron_Flooring_1k_8b",
            "Mahogany_Chevron_Flooring.mtlx",
        )
        # TODO: why do we not have to assign the material here?
        editor.qx_node_graph.load_graph_from_mx_file(mx_file)


if __name__ == "__main__":
    load_amd_copper_mtlx()
