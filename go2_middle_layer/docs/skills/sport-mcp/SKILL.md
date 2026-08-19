---
name: go2-sport-mcp
description: Use the GO2 robot sport MCP to control movement and posture. Use when the user wants the robot to move forward/backward, turn, step sideways, stand up/down, or stop moving.
---

# GO2 Sport MCP Skill

Use this skill when working with the GO2 middle layer sport endpoint to control the robot's movement and posture via the Unitree SDK2 sport client.

## Endpoint

| Environment | URL |
|-------------|-----|
| Local | `http://localhost:8001/sport/mcp` |
| Robot network | `http://172.168.20.189:8001/sport/mcp` |

**MCP protocol:** HTTP POST with JSON-RPC. Client must accept `application/json` and `text/event-stream` in the `Accept` header.

## Tools

| Tool | Parameters | Description |
|------|-------------|-------------|
| `stop_move` | none | Stop any current movement |
| `stand_up` | none | Stand up (recovers from lying/damping) |
| `stand_down` | none | Lie down (transitions through stand-up if needed) |
| `move_forward` | `distance: int` (cm, max 300) | Move straight forward. Uses depth camera for obstacle avoidance |
| `move_backward` | `distance: int` (cm, max 300) | Move straight backward |
| `turn_left` | `angle: int` (0–180°) | Turn left in place |
| `turn_right` | `angle: int` (0–180°) | Turn right in place |
| `step_to_left` | `distance: int` (cm, max 300) | Sidestep left |
| `step_to_right` | `distance: int` (cm, max 300) | Sidestep right |
| `move_to_target_position` | `angle: float` (-180–180°), `distance: float` (cm, max 300) | Turn to direction then walk forward. Angle 0=forward, + = left, − = right |

## Response Format

All tools return a `Response` object with `success`, `message`, `data`, `code`, `extra_data`.

## Usage Examples

| User intent | Tool call |
|-------------|-----------|
| "Stop" | `stop_move()` |
| "Stand up" | `stand_up()` |
| "Lie down" | `stand_down()` |
| "Go forward 50 cm" | `move_forward(distance=50)` |
| "Turn left 45 degrees" | `turn_left(angle=45)` |
| "Step right 30 cm" | `step_to_right(distance=30)` |
| "Move 45° left, 100 cm" | `move_to_target_position(angle=45, distance=100)` |

## Movement Defaults

| Parameter | Value |
|-----------|-------|
| Move speed | 0.4 m/s |
| Yaw speed | 0.5 rad/s |
| Obstacle avoidance | Stops if obstacle < 400 mm |

## Health Check

`GET http://localhost:8001/health` → `{"message": "OK"}`
