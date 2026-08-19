import base64
from typing import Optional, Tuple, Dict, Any
from dependency_injector.wiring import Provide, inject

from dependencies import Go2MiddleLayerContainer
from interfaces.camera import CameraService
from models.response import Response
import service_registry
import asyncio


_depth_description_semaphores: dict[int, asyncio.Semaphore] = {}


def _get_depth_description_semaphore(max_concurrency: int) -> asyncio.Semaphore:
    """
    Return a process-wide semaphore to limit concurrent depth description work.

    Args:
        max_concurrency: Maximum number of concurrent requests allowed to run the
            heavy `need_description=True` pipeline.
    """
    value = max(1, int(max_concurrency))
    sem = _depth_description_semaphores.get(value)
    if sem is None:
        sem = asyncio.Semaphore(value)
        _depth_description_semaphores[value] = sem
    return sem


class DepthCameraController:
    @inject
    async def capture_latest_image(
        self,
        camera_service: CameraService = Provide[
            Go2MiddleLayerContainer.depth_camera_service
        ],
        need_description: bool = False,
        description_max_concurrency: int = Provide[
            Go2MiddleLayerContainer.config.depth_camera.description_max_concurrency
        ],
    ) -> Response:
        """
        Get the latest frame from the background capture buffer and return base64 image.
        """
        reason = service_registry.get_unavailable_reason("depth_camera")
        if reason:
            return Response(
                success=False,
                message=f"Depth camera not available: {reason}",
                data=None,
                code=503,
            )

        if need_description:
            sem = _get_depth_description_semaphore(description_max_concurrency)
            async with sem:
                latest: Optional[Tuple[Dict[str, Any], bytes]] = (
                    await camera_service.get_latest_frame(need_description=True)
                )
        else:
            latest = await camera_service.get_latest_frame(need_description=False)
        if latest is None:
            return Response(
                success=False,
                message="No frame available yet. Background capture buffer is empty.",
                data=None,
                code=425,
            )
        info, img_bytes = latest

        if info is None or info.get("success") is False or img_bytes is None:
            return Response(
                success=False,
                message=f"Failed to capture frame from buffer. Message: {info.get('message') if info else None}",
                data=None,
                code=400,
            )

        image_data = base64.b64encode(img_bytes).decode("utf-8")
        return Response(
            success=True,
            message=f"Frame captured successfully from buffer. Message: {info.get('message') if info else None}",
            data=image_data,
            code=200,
            extra_data=info,
        )

    @inject
    def start_background_capture(
        self,
        camera_service: CameraService = Provide[
            Go2MiddleLayerContainer.depth_camera_service
        ],
        fps: int = 6,
    ) -> None:
        """
        Start the background capture of the depth camera.
        """
        return camera_service.start(fps=fps)

    @inject
    def stop_background_capture(
        self,
        camera_service: CameraService = Provide[
            Go2MiddleLayerContainer.depth_camera_service
        ],
    ) -> None:
        """
        Stop the background capture of the depth camera.
        """
        return camera_service.stop()
