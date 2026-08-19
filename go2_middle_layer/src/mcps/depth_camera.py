import logging
import time

from fastmcp import FastMCP
from models.response import Response
from usecases.depth_camera_controller import DepthCameraController


logger = logging.getLogger("MCP:DepthCamera")

mcp = FastMCP("depth_camera")

depth_camera_controller = DepthCameraController()


@mcp.tool(
    description="Capture current frame from robot's depth camera (from background buffer). If need_description is True, the response will include natural language description of the detected objects."
)
async def capture_image(need_description: bool = False) -> Response:
    """
    Get the latest frame from the background capture buffer.
    """
    start_time = time.time()
    res = await depth_camera_controller.capture_latest_image(
        need_description=need_description
    )
    end_time = time.time()
    logger.info(
        f"[Depth Camera MCP Tools] Total time for calling tool: {end_time - start_time}"
    )
    return res


def start_depth_camera_background_capture(fps: int = 6) -> None:
    return depth_camera_controller.start_background_capture(fps=fps)


def stop_depth_camera_background_capture() -> None:
    return depth_camera_controller.stop_background_capture()


if __name__ == "__main__":
    mcp.run()
