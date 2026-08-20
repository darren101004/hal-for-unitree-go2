def __getattr__(name):
    """Lazy re-export — unitree SDK is only imported on first access."""
    if name == "SdkSportStateService":
        try:
            from impl.state.sdk_state_service import SdkSportStateService

            return SdkSportStateService
        except Exception:
            from impl.state.sdk_state_service_stub import (
                SdkSportStateServiceStub as SdkSportStateService,
            )

            return SdkSportStateService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "SdkSportStateService",
]
