"""
Stub implementation of DepthCameraService when pyrealsense2 is not installed.
Use this to run the server without an Intel RealSense camera.
"""

import logging
from typing import Optional, Tuple, Dict, Any

from interfaces.camera import CameraService
import service_registry

logger = logging.getLogger("Camera:DepthCameraServiceStub")

_REASON = "pyrealsense2 not installed. Install with: conda install -c conda-forge pyrealsense2"


class DepthCameraServiceStub(CameraService):
    """
    No-op depth camera service when pyrealsense2 is not available.
    All capture operations return "not available" responses.
    """

    def __init__(self, config: dict | None = None) -> None:
        self._config = config
        logger.warning("Depth camera disabled: %s", _REASON)
        service_registry.register("depth_camera", False, _REASON)

    def is_healthy(self) -> bool:
        """Stub is never healthy — device not available."""
        return False

    def restart(self) -> None:
        """No-op for stub."""
        pass

    def start(self, fps: int = 30) -> None:
        """No-op when depth camera is not available."""
        pass

    def stop(self) -> None:
        """No-op when depth camera is not available."""
        pass

    async def get_latest_frame(
        self, need_description: bool = False
    ) -> Optional[Tuple[Dict[str, Any], bytes]]:
        """
        Return None so the controller responds with "No frame available".
        """
        return None, None

    async def get_latest_distance_to_center(self) -> Optional[float]:
        """
        Return None when depth camera is not available.
        """
        return None
