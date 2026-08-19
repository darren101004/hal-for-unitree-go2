def __getattr__(name):
    """Lazy re-exports — heavy dependencies (rclpy, unitree) are only imported on first access."""
    if name == "Ros2EchoSportStateService":
        from impl.state.echo_state_service import Ros2EchoSportStateService

        return Ros2EchoSportStateService
    if name == "Ros2SportStateService":
        try:
            from impl.state.ros2_state_service import Ros2SportStateService

            return Ros2SportStateService
        except Exception:
            from impl.state.ros2_state_service_stub import (
                Ros2SportStateServiceStub as Ros2SportStateService,
            )

            return Ros2SportStateService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Ros2EchoSportStateService",
    "Ros2SportStateService",
]
