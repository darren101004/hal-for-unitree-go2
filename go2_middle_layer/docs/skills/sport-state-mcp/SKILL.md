---
name: go2-sport-state-mcp
description: Use the GO2 robot sport state MCP to read real-time robot state (position, velocity, IMU, foot force, etc.). Use when the user wants to know the robot's current pose, movement status, or sensor data.
---

# GO2 Sport State MCP Skill

Use this skill when working with the GO2 middle layer sport state endpoint to read the robot's real-time state from the ROS2 topic `/lf/sportmodestate`.

## Endpoint

| Environment | URL |
|-------------|-----|
| Local | `http://localhost:8001/sport_state/mcp` |
| Robot network | `http://172.168.20.189:8001/sport_state/mcp` |

**MCP protocol:** HTTP POST with JSON-RPC. Client must accept `application/json` and `text/event-stream` in the `Accept` header.

## Tools

| Tool | Parameters | Description |
|------|-------------|-------------|
| `get_sport_mode_state` | none | Get latest robot state (uses echo backend) |
| `get_sport_mode_state_using_echo` | none | Get state via ros2 topic echo subprocess |
| `get_sport_mode_state_using_ros2` | none | Get state via native ROS2 subscriber node |

## Response Data

`data` contains `RobotState`:

```json
{
  "sportmodestate": {
    "stamp": { "sec": 1234567890, "nanosec": 123456789 },
    "error_code": 0,
    "imu_state": { "quaternion": [w,x,y,z], "gyroscope": [gx,gy,gz], "accelerometer": [ax,ay,az], "rpy": [roll,pitch,yaw] },
    "mode": 1,
    "position": [x, y, z],
    "velocity": [vx, vy, vz],
    "body_height": 0.3,
    "foot_force": [fl, fr, rl, rr],
    "range_obstacle": [front, right, back, left]
  },
  "lowstate": {}
}
```

## Sport Mode Values

| Value | Mode |
|-------|------|
| 0 | Idle |
| 1 | Standing |
| 2 | Walking (velocity) |
| 3 | Walking (position) |
| 5 | Stand down |
| 6 | Stand up |
| 7 | Damping |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `STATE_SERVICE_MODE` | `echo` | `echo` or `ros2` |
| `STATE_TOPIC` | `/lf/sportmodestate` | ROS2 topic |

## Health Check

`GET http://localhost:8001/health` → `{"message": "OK"}`
