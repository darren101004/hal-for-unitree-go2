"""
Stub implementation of SdkSportStateService when unitree_sdk2py is not installed.
Use this to run the server without the GO2 robot.
"""

import logging
from typing import Optional

from interfaces.state import StateService
from models.state import RobotState
import service_registry

logger = logging.getLogger("State:SdkSportStateServiceStub")

_REASON = (
    "unitree_sdk2py not installed. Install unitree_sdk2_python to enable robot state reading."
)


class SdkSportStateServiceStub(StateService):
    """
    No-op state service when unitree_sdk2py is not available.
    All state operations return None.
    """

    def __init__(
        self,
        sport_topic: str = "/lf/sportmodestate",
        lowstate_topic: str = "/lowstate",
        lowstate_min_update_interval_sec: float = 120.0,
        network_interface: str = "end0",
        queue_size: int = 10,
    ) -> None:
        self._sport_topic = sport_topic
        self._lowstate_topic = lowstate_topic
        self._lowstate_min_update_interval_sec = float(lowstate_min_update_interval_sec)
        self._network_interface = network_interface
        self._queue_size = int(queue_size)
        logger.warning("State service disabled: %s", _REASON)
        service_registry.register(
            "state",
            False,
            _REASON,
            extra_data={
                "network_interface": self._network_interface,
                "sport_topic": self._sport_topic,
                "lowstate_topic": self._lowstate_topic,
            },
        )

    def is_healthy(self) -> bool:
        """Stub is never healthy — SDK not available."""
        return False

    def restart(self) -> None:
        """No-op for stub."""
        pass

    def start(self) -> None:
        """No-op when the SDK is not available."""
        pass

    def stop(self) -> None:
        """No-op when the SDK is not available."""
        pass

    def get_latest_state(self) -> Optional[RobotState]:
        """Return None when the SDK is not available."""
        return None
