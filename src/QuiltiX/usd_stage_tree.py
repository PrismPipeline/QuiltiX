import os
import sys

from qtpy import QtWidgets, QtCore, QtGui  # type: ignore

from pxr import Usd, UsdGeom
from QuiltiX import usd_stage
from QuiltiX.constants import ROOT

EYE_VISABLE = os.path.join(ROOT, "resources", "icons", "eye_visible.svg")
EYE_INVISABLE = os.path.join(ROOT, "resources", "icons", "eye_invisible.svg")


class PrimVisButton(QtWidgets.QToolButton):
    def __init__(self, parent=None):
        super(PrimVisButton, self).__init__()
        self.setStyleSheet("padding: 0px; margin: 0px; background-color: rgba(255, 255, 255, 0);")

        # TODO: only have one QIcon for all buttons
        self.vis_icon = QtGui.QIcon(EYE_VISABLE)
        self.invis_icon = QtGui.QIcon(EYE_INVISABLE)

        self.vis = True
        self.setIcon(self.vis_icon)
        self.setFixedSize(14, 14)
        # self.clicked.connect(self.toggle_visibility)

    def toggle_visibility(self):
        self.vis = not self.vis
        self.update_vis_icon()
        return self.vis

    def update_vis_icon(self):
        if self.vis:
            self.setIcon(self.vis_icon)
        else:
            self.setIcon(self.invis_icon)

    def set_visibility(self, visibility):
        self.vis = visibility
        self.update_vis_icon()
        return self.vis


class PrimItemWidget(QtWidgets.QTreeWidgetItem):
    def __init__(self, prim):
        super(PrimItemWidget, self).__init__()
        self.prim = prim

    def data(self, column, role):
        if column == 0:
            if role == QtCore.Qt.DisplayRole:
                return self.prim.GetName()
                # return "foo"
        return super().data(column, role)


class UsdStageTreeWidget(QtWidgets.QTreeWidget):
    def __init__(self, stage=None, parent=None):
        super(UsdStageTreeWidget, self).__init__(parent=parent)
        # TODO: cleanup settings
        __qtreewidgetitem = QtWidgets.QTreeWidgetItem()
        __qtreewidgetitem.setText(0, "StagePath")
        __qtreewidgetitem.setTextAlignment(2, QtCore.Qt.AlignLeading | QtCore.Qt.AlignVCenter)
        self.setHeaderItem(__qtreewidgetitem)
        self.setColumnCount(2)
        self.header().setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.header().setStretchLastSection(False)
        self.header().setVisible(False)
        self.header().setSectionResizeMode(
            0, QtWidgets.QHeaderView.Stretch
        )
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setFrameShadow(QtWidgets.QFrame.Plain)
        self.setLineWidth(0)
        self.setMidLineWidth(0)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setUniformRowHeights(True)
        self.setColumnWidth(1, 10)
        self._prim_to_item_map = {}
        self.set_stage(stage)

    def set_stage(self, stage):
        self.stage = stage
        self.refresh_tree()

    def refresh_tree(self):
        # mods = QtWidgets.QApplication.keyboardModifiers()
        # if mods != QtCore.Qt.ControlModifier:
        #     return

        self.clear()
        if not self.stage:
            return

        stage_root = self.stage.GetPseudoRoot()
        invisible_root_item = self.invisibleRootItem()
        self.populate_item_tree(stage_root, invisible_root_item)
        self.expandToDepth(0)

    def create_item_from_prim(self, prim):
        item = PrimItemWidget(prim)
        item.emitDataChanged()
        self._prim_to_item_map[prim] = item
        return item

    def populate_item_tree(self, prim, parent_item):
        created_item = self.create_item_from_prim(prim)
        parent_item.addChild(created_item)

        # FIXME: this will probably not work in all cases
        if bool(UsdGeom.Imageable(prim).GetVisibilityAttr()):
            vis_button = PrimVisButton(prim)
            vis_button.clicked.connect(lambda: self.toggle_hierarchy_visibility(created_item))
            self.setItemWidget(created_item, 1, vis_button)

        prim_children = self._get_filtered_prim_children(prim)
        for prim_child in prim_children:
            self.populate_item_tree(prim_child, created_item)

        return created_item

    def _get_filtered_prim_children(self, prim):
        return prim.GetFilteredChildren(Usd.PrimIsActive)

    def toggle_hierarchy_visibility(self, item, set_visibility_to=None):
        item_vis_button = self.itemWidget(item, 1)
        if set_visibility_to is None:
            set_visibility_to = item_vis_button.toggle_visibility()
        else:
            item_vis_button.set_visibility(set_visibility_to)

        # TODO: hide stage prims

        for i in range(item.childCount()):
            child_item = item.child(i)
            self.toggle_hierarchy_visibility(child_item, set_visibility_to)

    def get_selected_prims(self):
        items = self.selectedItems()
        prims = [item.prim for item in items]
        return prims


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    stage_file = os.path.join(ROOT, "resources", "geometry", "plane_uv.usda")
    stage = usd_stage.get_stage_from_file(stage_file)
    tree_widget = UsdStageTreeWidget(stage)
    tree_widget.show()
    app.exec_()
