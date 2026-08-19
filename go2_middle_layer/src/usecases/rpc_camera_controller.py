import base64
from typing import Optional, Tuple, Dict, Any
from dependency_injector.wiring import Provide, inject
from dependencies import Go2MiddleLayerContainer

from interfaces.camera import CameraService
from models.response import Response
import service_registry


class RpcCameraController:

    @inject
    async def capture_latest_image(
        self,
        camera_service: CameraService = Provide[
            Go2MiddleLayerContainer.rpc_camera_service
        ],
        need_description: bool = False,
    ) -> Response:
        """
        Get the latest frame from background buffer and return base64 image.
        """
        reason = service_registry.get_unavailable_reason("rpc_camera")
        if reason:
            return Response(
                success=False,
                message=f"RPC camera not available: {reason}",
                data=None,
                code=503,
            )

        frame: Optional[Tuple[Dict[str, Any], bytes]] = (
            await camera_service.get_latest_frame(need_description=need_description)
        )
        if frame is None:
            return Response(
                success=False,
                message="No image available yet. Background capture buffer is empty.",
                data=None,
                code=425,
            )

        info, data = frame
        code = info.get("code", 1)
        if code != 0 or data is None:
            return Response(
                success=False,
                message=f"Failed to capture image from buffer. Code: {code}",
                data=None,
                code=400,
            )

        image_data = base64.b64encode(data).decode("utf-8")
        return Response(
            success=True,
            message=f"Image captured successfully from buffer. Code: {code}",
            data=image_data,
            code=200,
        )

    @inject
    def start_background_capture(
        self,
        camera_service: CameraService = Provide[
            Go2MiddleLayerContainer.rpc_camera_service
        ],
        fps: int = 30,
    ) -> None:
        """
        Start the background capture of the camera.
        """
        return camera_service.start(fps=fps)

    @inject
    def stop_background_capture(
        self,
        camera_service: CameraService = Provide[
            Go2MiddleLayerContainer.rpc_camera_service
        ],
    ) -> None:
        """
        Stop the background capture of the camera.
        """
        return camera_service.stop()
