def __getattr__(name):
    """Lazy re-export — unitree video SDK is only imported on first access."""
    if name == "RpcCameraService":
        try:
            from impl.rpc_camera.rpc_camera_service import RpcCameraService

            return RpcCameraService
        except ImportError:
            from impl.rpc_camera.rpc_camera_service_stub import RpcCameraServiceStub

            return RpcCameraServiceStub
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["RpcCameraService"]
