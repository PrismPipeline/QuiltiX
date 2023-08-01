import os

from QuiltiX import constants
from tests import helpers


def create_standard_surface():
    with helpers.quiltix_instance() as editor:
        with editor.qx_node_graph.block_save():
            surf_node = editor.qx_node_graph.create_node("Pbr.standard_surface")
            mat_node = editor.qx_node_graph.create_node("Material.surfacematerial")
            tex_node = editor.qx_node_graph.create_node("Texture2d.image")
            tex_node.change_type("color3")
            path = os.path.join(
                constants.ROOT,
                "resources",
                "materials",
                "Wooden_Flooring_004_1k_8b",
                "textures",
                "baseColor.png",
            )
            tex_node.set_property("file", path)
            mat_node.set_input(0, surf_node.get_output(0))
            surf_node.set_input(1, tex_node.get_output(0))
            editor.qx_node_graph.auto_layout_nodes(editor.qx_node_graph.all_nodes(), down_stream=True)

        editor.properties.add_selected_node()
        editor.qx_node_graph.update_mx_xml_data_from_graph()
        editor.stage_ctrl.apply_first_material_to_all_prims()


if __name__ == "__main__":
    create_standard_surface()
