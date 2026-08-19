import logging

from fastmcp import FastMCP

from models.response import Response
from usecases.rpc_camera_controller import RpcCameraController

logger = logging.getLogger("MCP:RpcCamera")

rpc_camera_controller = RpcCameraController()
mcp = FastMCP("camera")


@mcp.tool(
    description="Capture current frame from robot's camera (from background buffer)"
)
async def capture_image(need_description: bool = False) -> Response:
    return await rpc_camera_controller.capture_latest_image(
        need_description=need_description
    )


def start_rpc_camera_background_capture(fps: int = 30) -> None:
    return rpc_camera_controller.start_background_capture(fps=fps)


def stop_rpc_camera_background_capture() -> None:
    return rpc_camera_controller.stop_background_capture()


if __name__ == "__main__":
    mcp.run()
