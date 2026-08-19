def __getattr__(name):
    """Lazy re-export — cv2 is only imported on first access."""
    if name == "LocalCameraService":
        from impl.local_camera.local_camera_service import LocalCameraService

        return LocalCameraService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["LocalCameraService"]
