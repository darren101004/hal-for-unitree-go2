"""
Stub implementation of SdkSportService when unitree_sdk2py is not installed.
Use this to run the server without the GO2 robot.
"""

import logging

from interfaces.sport import SportService
from models.response import Response
from models.sport_request import SportRequest
import service_registry

logger = logging.getLogger("Sport:SdkSportServiceStub")

_REASON = (
    "unitree_sdk2py not installed. Install unitree_sdk2_python to enable robot control."
)


class SdkSportServiceStub(SportService):
    """
    No-op sport service when unitree_sdk2py is not available.
    Returns error response for all commands.
    """

    def __init__(self, network_interface: str = "eth0") -> None:
        logger.warning("Sport service disabled: %s", _REASON)
        service_registry.register("sport", False, _REASON)

    def is_healthy(self) -> bool:
        """Stub is never healthy — SDK not available."""
        return False

    def restart(self) -> None:
        """No-op for stub."""
        pass

    def handle(self, request: SportRequest) -> Response:
        """Return error when unitree_sdk2py is not available."""
        return Response(
            success=False,
            message=f"Sport service not available: {_REASON}",
            data=None,
            code=503,
        )
