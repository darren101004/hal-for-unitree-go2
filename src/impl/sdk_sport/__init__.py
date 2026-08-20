def __getattr__(name):
    """Lazy re-export — unitree SDK is only imported on first access."""
    if name == "SdkSportService":
        try:
            from impl.sdk_sport.sdk_sport_service import SdkSportService

            return SdkSportService
        except ImportError:
            from impl.sdk_sport.sdk_sport_service_stub import SdkSportServiceStub

            return SdkSportServiceStub
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["SdkSportService"]
