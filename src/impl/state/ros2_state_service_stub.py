"""
Stub implementation of Ros2SportStateService when rclpy (ROS2) is not installed.
Use this to run the server without ROS2.
"""

import logging
from typing import Optional

from interfaces.state import StateService
from models.state import RobotState
import service_registry

logger = logging.getLogger("State:Ros2SportStateServiceStub")

_REASON = "rclpy not installed. Install ROS2 and rclpy to enable robot state reading."


class Ros2SportStateServiceStub(StateService):
    """
    No-op ROS2 state service when rclpy is not available.
    All state operations return None.
    """

    def __init__(
        self,
        sport_topic: str = "/lf/sportmodestate",
        lowstate_topic: str = "/lowstate",
        lowstate_min_update_interval_sec: float = 120.0,
        queue_size: int = 10,
    ) -> None:
        """
        Create a stub that disables ROS2 state reading.

        Args:
            sport_topic: ROS2 topic for sport mode state.
            lowstate_topic: ROS2 topic for lowstate.
            lowstate_min_update_interval_sec: Minimum interval for lowstate updates.
            queue_size: Max queue size (ignored in stub).
        """
        self._sport_topic = sport_topic
        self._lowstate_topic = lowstate_topic
        self._lowstate_min_update_interval_sec = float(lowstate_min_update_interval_sec)
        self._queue_size = int(queue_size)
        logger.warning("ROS2 state service disabled: %s", _REASON)
        service_registry.register(
            "state_ros2",
            False,
            _REASON,
            extra_data={
                "sport_topic": self._sport_topic,
                "lowstate_topic": self._lowstate_topic,
                "lowstate_min_update_interval_sec": self._lowstate_min_update_interval_sec,
                "queue_size": self._queue_size,
            },
        )

    def is_healthy(self) -> bool:
        """Stub is never healthy — ROS2 not available."""
        return False

    def restart(self) -> None:
        """No-op for stub."""
        pass

    def start(self) -> None:
        """No-op when ROS2 is not available."""
        pass

    def stop(self) -> None:
        """No-op when ROS2 is not available."""
        pass

    def get_latest_state(self) -> Optional[RobotState]:
        """Return None when ROS2 is not available."""
        return None
