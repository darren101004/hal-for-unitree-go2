import logging

from fastmcp import FastMCP

from models.response import Response
from usecases.sport_controller import SportController

logger = logging.getLogger("MCP:Sport")

mcp = FastMCP("sport")

sport_controller = SportController()


@mcp.tool(description="Sport command: Stop Move")
async def stop_move() -> Response:
    return await sport_controller.stop_move()


@mcp.tool(description="Sport command: Stand Up")
async def stand_up() -> Response:
    return await sport_controller.stand_up()


@mcp.tool(description="Sport command: Stand Down")
async def stand_down() -> Response:
    return await sport_controller.stand_down()


@mcp.tool(
    description="Move forward (distance in centimeters), Maximum distance: 300 cm. Move straight ahead in the current forward-facing direction; the robot will go forward directly in front of its field of view."
)
async def move_forward(distance: int) -> Response:
    return await sport_controller.move_forward(distance)


@mcp.tool(
    description="Move backward (distance in centimeters), Maximum distance: 300 cm. Move backward in the current backward-facing direction; the robot will go backward directly behind its field of view."
)
async def move_backward(distance: int) -> Response:
    return await sport_controller.move_backward(distance)


@mcp.tool(
    description="Turn left (angle in degrees) in place (angle range: [0, 180] degrees). Example: turn_left(45) will turn left 45 degrees."
)
async def turn_left(angle: int) -> Response:
    return await sport_controller.turn_left(angle)


@mcp.tool(
    description="Turn right (angle in degrees) in place (angle range: [0, 180] degrees). Example: turn_right(45) will turn right 45 degrees."
)
async def turn_right(angle: int) -> Response:
    return await sport_controller.turn_right(angle)


@mcp.tool(
    description="Step to left (distance in centimeters), Maximum distance: 300 cm. Example: step_to_left(30) will step to the left 30 centimeters."
)
async def step_to_left(distance: int) -> Response:
    return await sport_controller.step_left(distance)


@mcp.tool(
    description="Step to right (distance in centimeters), Maximum distance: 300 cm. Example: step_to_right(30) will step to the right 30 centimeters."
)
async def step_to_right(distance: int) -> Response:
    return await sport_controller.step_right(distance)


@mcp.tool(
    description="Move to target position (angle in degrees and distance in centimeters), Angle range: [-180, 180] degrees, Angle 0 means facing forward, Angle positive means facing left side, Angle negative means facing right side, Maximum distance: 300 cm. Example: move_to_target_position(45, 100) will move to the target position 45 degrees at the left side and 100 centimeters."
)
async def move_to_target_position(angle: float, distance: float) -> Response:
    angle = min(max(angle, -180), 180)
    distance = min(max(distance, 0), 300)
    return await sport_controller.move_to_target_position(angle, distance)


def start_sport_service() -> None:
    """Force lazy DI instantiation so the sport service registers its availability."""
    sport_controller.warm_up()


if __name__ == "__main__":
    mcp.run()
