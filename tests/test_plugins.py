def test_load_plugin_materialxjson(materialxjson_plugin, quiltix_instance):
    assert quiltix_instance.json_serializer
    assert "mimetype" in quiltix_instance.json_serializer.get_json_from_graph()
    assert quiltix_instance.json_serializer.get_json_from_graph()["mimetype"] == "application/mtlx+json"
