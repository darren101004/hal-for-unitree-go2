"""
Facade for depth camera service. Uses real implementation when pyrealsense2
is installed, otherwise falls back to stub so the server can run without RealSense.
"""


def __getattr__(name):
    """Lazy re-export — pyrealsense2/cv2 are only imported on first access."""
    if name == "DepthCameraService":
        try:
            from impl.depth_camera.depth_camera_service import DepthCameraService

            return DepthCameraService
        except ImportError:
            from impl.depth_camera.depth_camera_service_stub import (
                DepthCameraServiceStub,
            )

            return DepthCameraServiceStub
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["DepthCameraService"]
