import logging

from fastmcp import FastMCP

from models.response import Response
from usecases.local_camera_controller import LocalCameraController

logger = logging.getLogger("MCP:LocalCamera")

local_camera_controller = LocalCameraController()
mcp = FastMCP("local_camera")


@mcp.tool(
    description="Capture current frame from local camera (from background buffer)"
)
async def capture_image(need_description: bool = False) -> Response:
    """
    Capture current frame from local camera (from background buffer).
    Note: No description is supported for local camera.
    """
    return await local_camera_controller.capture_latest_image(
        need_description=need_description
    )


def start_local_camera_background_capture(fps: int = 30) -> None:
    return local_camera_controller.start_background_capture(fps=fps)


def stop_local_camera_background_capture() -> None:
    return local_camera_controller.stop_background_capture()


if __name__ == "__main__":
    mcp.run()
