import logging
from fastmcp import FastMCP

from models.response import Response
from usecases.state_controller import StateController

logger = logging.getLogger("MCP:SportState")

state_controller = StateController()
mcp = FastMCP("state")


@mcp.tool(description="Get Robot Sport Mode State")
async def get_sport_mode_state() -> Response:
    return await state_controller.get_latest_state()


@mcp.tool(
    description=(
        "Deprecated alias of get_sport_mode_state. State no longer comes from a "
        "ROS2 node — it is read straight from DDS via the Unitree SDK."
    )
)
async def get_sport_mode_state_using_ros2() -> Response:
    return await state_controller.get_latest_state()


def start_state_background_reader() -> None:
    return state_controller.start_state_service()


def stop_state_background_reader() -> None:
    return state_controller.stop_state_service()
