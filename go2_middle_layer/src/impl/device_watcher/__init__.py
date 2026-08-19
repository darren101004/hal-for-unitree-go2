def __getattr__(name):
    """Lazy re-export."""
    if name == "DeviceWatcherService":
        from impl.device_watcher.device_watcher_service import DeviceWatcherService

        return DeviceWatcherService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["DeviceWatcherService"]
