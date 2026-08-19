"""
Stub implementation of RpcCameraService when unitree_sdk2py is not installed.
Use this to run the server without the GO2 robot.
"""

import logging
from typing import Optional, Tuple, Dict, Any

from interfaces.camera import CameraService
import service_registry

logger = logging.getLogger("Camera:RpcCameraServiceStub")

_REASON = (
    "unitree_sdk2py not installed. Install unitree_sdk2_python to enable robot camera."
)


class RpcCameraServiceStub(CameraService):
    """
    No-op RPC camera service when unitree_sdk2py is not available.
    """

    def __init__(self, network_interface: str) -> None:
        self._network_interface = network_interface
        logger.warning("RPC camera disabled: %s", _REASON)
        service_registry.register("rpc_camera", False, _REASON)

    def is_healthy(self) -> bool:
        """Stub is never healthy — SDK not available."""
        return False

    def restart(self) -> None:
        """No-op for stub."""
        pass

    def start(self, fps: int = 30) -> None:
        """No-op when unitree_sdk2py is not available."""
        pass

    def stop(self) -> None:
        """No-op when unitree_sdk2py is not available."""
        pass

    async def get_latest_frame(
        self, need_description: bool = False
    ) -> Optional[Tuple[Dict[str, Any], bytes]]:
        """Return None when unitree_sdk2py is not available."""
        return None
