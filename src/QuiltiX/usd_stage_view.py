import os
import logging

from QuiltiX.constants import ROOT
from QuiltiX.usd_stage import set_pxr_mtlx_stdlib_search_paths
from pxr.Usdviewq.stageView import StageView # type: ignore

from qtpy.QtCore import QSize  # type: ignore
from qtpy.QtCore import Qt, Signal  # type: ignore
from qtpy.QtWidgets import QVBoxLayout, QWidget  # type: ignore

set_pxr_mtlx_stdlib_search_paths()
from QuiltiX.usd_stage import create_empty_stage, create_stage_with_hdri, get_stage_from_file # noqa: E402 

logger = logging.getLogger(__name__)


class StageViewWidget(QWidget):
    keyPressed = Signal(object, object)
    fileDropped = Signal(object)
    rendererChanged = Signal(object)

    def __init__(self, stage=None, window_title="USD Stageview"):
        super(StageViewWidget, self).__init__()

        self.model = StageView.DefaultDataModel()
        self.model.viewSettings.showHUD = False

        self.view = StageView(dataModel=self.model)

        # [usdviewq] Workaround apparent PySide6 GL bug https://github.com/PixarAnimationStudios/OpenUSD/commit/abb175da3587d3e21111f0d0b753fb2dd965d7dc
        from OpenGL import GL
        oldPaintGL = StageView.paintGL
        def paintGLFix(self):
            GL.glDepthMask(GL.GL_TRUE)
            oldPaintGL(self)

        StageView.paintGL = paintGLFix

        self.view.orig_handleRendererChanged = self.view._handleRendererChanged
        self.view._handleRendererChanged = self._handleRendererChanged

        # Disable Orgin Axis/Gizmo, but store original function in case we need it sometime
        self.view.ODrawAxis = self.view.DrawAxis
        self.view.DrawAxis = lambda _: None

        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.WheelFocus)
        self.setObjectName("prism")

        self.view._dataModel.viewSettings.showAABBox = False
        self.view._dataModel.viewSettings.showOBBox = False

        # if not stage:
        #     stage = create_empty_stage()

        hdri_path = os.path.join(ROOT, "resources", "hdris", "dreifaltigkeitsberg_1k.hdr")
        self.set_hdri(hdri_path)
        if stage:
            self.set_stage(stage)

        self._stage = self.get_stage()
        self._stage_root = self.get_stage_root()

        # Override default clipping planes/range to be more suitable for smaller objects like shader balls
        self.override_free_cam_near(0.1)
        self.override_free_cam_far(200000.0)

    def sizeHint(self):
        return QSize(500, 400)

    @property
    def stage(self):
        return self._stage

    def get_stage(self):
        return self.model.stage

    @property
    def stage_root(self):
        return self._stage_root

    def get_stage_root(self):
        if self.model.stage:
            return self.model.stage.GetRootLayer()
        else:
            return None

    def set_stage(self, stage, add_hdri=True):
        self.view.setUpdatesEnabled(False)
        curRendererId = self.view.GetCurrentRendererId()
        self.view.closeRenderer()
        self.view._dataModel.stage = None
        self.view._dataModel._clearCaches()
        self.model.stage = stage
        self._stage = self.model.stage
        self._stage_root = self.get_stage_root()
        if add_hdri:
            self.set_hdri_enabled(add_hdri)

        self.view._dataModel.viewSettings.freeCamera.rotTheta = -45
        self.view._dataModel.viewSettings.freeCamera.rotPhi = 15
        dftRenderer = self.view.GetCurrentRendererId()
        if dftRenderer != curRendererId and curRendererId:
            self.view.SetRendererPlugin(curRendererId)
            self.apply_rendersettings_to_current_delegate()

        self.view.setUpdatesEnabled(True)
        self.view.updateView(resetCam=True, forceComputeBBox=True)

    def set_stage_from_file(self, file_path):
        stage = get_stage_from_file(file_path)
        self.set_stage(stage)

    def get_current_renderer(self):
        if not self.view._renderer:
            return

        return self.view._renderer.GetCurrentRendererId()

    def get_current_renderer_name(self):
        return self.view._renderer.GetRendererDisplayName(self.get_current_renderer())

    def set_current_renderer(self, renderer_id):
        if not renderer_id == self.get_current_renderer():
            return self.view.SetRendererPlugin(renderer_id)

    def set_current_renderer_by_name(self, renderer_name):
        renderer_map = self.get_available_renderer_plugin_map()
        if renderer_name not in renderer_map:
            logger.error(f"Could not set renderer with name {renderer_name}. It is not available.")
            return
        
        renderer_id = renderer_map[renderer_name]
        result = self.set_current_renderer(renderer_id)
        if result:
            self.apply_rendersettings_to_current_delegate()

    def _handleRendererChanged(self, rendererId):
        self.view.orig_handleRendererChanged(rendererId)
        self.apply_rendersettings_to_current_delegate()
        self.rendererChanged.emit(rendererId)

    def apply_rendersettings_to_current_delegate(self):
        renderer_id = self.get_current_renderer()
        if renderer_id == "HdRedshiftRendererPlugin":
            self.view.SetRendererSetting("redshift:global:ProgressiveRenderingEnabled", True)
            self.view.SetRendererSetting("redshift:global:RS_log_level", "Warning")
            self.view._dataModel.viewSettings.ambientLightOnly = False
        elif renderer_id == "BRAY_HdKarma":
            self.view.SetRendererSetting("karma:global:engine", "xpu")

    def get_available_renderer_plugin_names(self):
        renderer_plugin_names = []
        renderer_plugin_ids = self.get_available_renderer_plugin_ids()
        for renderer_plugin_id in renderer_plugin_ids:
            renderer_display_name = self.view._renderer.GetRendererDisplayName(renderer_plugin_id)
            renderer_plugin_names.append(renderer_display_name)

        return renderer_plugin_names

    def get_available_renderer_plugin_ids(self):
        return self.view._renderer.GetRendererPlugins()

    def get_available_renderer_plugin_map(self):
        renderer_plugin_map = {}
        renderer_plugin_ids = self.get_available_renderer_plugin_ids()
        for renderer_plugin_id in renderer_plugin_ids:
            renderer_display_name = self.view._renderer.GetRendererDisplayName(renderer_plugin_id)
            renderer_plugin_map[renderer_display_name] = renderer_plugin_id

        return renderer_plugin_map

    def set_hdri(self, path):
        was_enabled = False
        if hasattr(self, "hdri_stage") and self.hdri_stage.GetRootLayer().identifier in self._stage_root.subLayerPaths:
            self._stage_root.subLayerPaths.remove(self.hdri_stage.GetRootLayer().identifier)
            was_enabled = True

        self.hdri_stage = create_stage_with_hdri(path)
        if was_enabled:
            self.set_hdri_enabled(True)

    def set_hdri_enabled(self, enabled):
        if enabled:
            self._stage_root.subLayerPaths.append(self.hdri_stage.GetRootLayer().identifier)
            logger.info("added hdri to stage")
        else:
            self._stage_root.subLayerPaths.remove(self.hdri_stage.GetRootLayer().identifier)
            logger.info("removed hdri from stage")

        self.view.updateView(resetCam=False, forceComputeBBox=False)

    def closeEvent(self, event):
        self.view.closeRenderer()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_F:
            self.view.updateView(resetCam=True, forceComputeBBox=True)

        self.keyPressed.emit(self, key)

    def enterEvent(self, event):
        self.setFocus()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            e.setDropAction(Qt.LinkAction)
            e.accept()

            files = [os.path.normpath(str(url.toLocalFile())) for url in e.mimeData().urls()]
            self.fileDropped.emit(files[0])
        else:
            e.ignore()

    def override_free_cam_near(self, near):
        self.model.viewSettings.freeCameraOverrideNear = near

    def override_free_cam_far(self, far):
        self.model.viewSettings.freeCameraOverrideFar = far
