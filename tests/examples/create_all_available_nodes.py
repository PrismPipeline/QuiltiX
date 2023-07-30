from tests import helpers


def create_all_available_nodes():
    with helpers.quiltix_instance() as editor:
        with editor.qx_node_graph.block_save():
            for qx_node in editor.qx_node_graph.registered_nodes():
                editor.qx_node_graph.create_node(qx_node)
            editor.qx_node_graph.auto_layout_nodes()


if __name__ == "__main__":
    create_all_available_nodes()
