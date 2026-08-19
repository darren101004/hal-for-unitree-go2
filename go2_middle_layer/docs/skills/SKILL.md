# Go2 Robot Dog Control

You have access to a Unitree Go2 quadruped robot via 7 MCP servers running at `http://172.168.20.189:8001`.
Use these tools to move the robot, read its state, capture camera images, and capture voice commands.

All responses follow a unified format:
```json
{ "success": bool, "message": string, "data": any, "code": int, "extra_data": object|null }
```

---

## MCP Server: `go2-sport` — Movement Commands

Endpoint: `http://172.168.20.189:8001/sport/mcp`

Use this server when the user asks the robot to move, walk, turn, stop, stand, or go somewhere.

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `stop_move` | none | Stop all movement immediately |
| `stand_up` | none | Stand up from sitting/lying position |
| `stand_down` | none | Sit/lie down from standing position |
| `move_forward` | `distance: int` (cm, max 300) | Move straight forward |
| `move_backward` | `distance: int` (cm, max 300) | Move straight backward |
| `turn_left` | `angle: int` (degrees, 0–180) | Turn left in place |
| `turn_right` | `angle: int` (degrees, 0–180) | Turn right in place |
| `step_to_left` | `distance: int` (cm, max 300) | Sidestep to the left |
| `step_to_right` | `distance: int` (cm, max 300) | Sidestep to the right |
| `move_to_target_position` | `angle: float` (degrees, -180 to 180), `distance: float` (cm, max 300) | Move to a target position. Angle 0 = forward, positive = left, negative = right |

### Examples
- "Go forward 1 meter" → `move_forward(distance=100)`
- "Turn left 90 degrees" → `turn_left(angle=90)`
- "Move to the object at 45 degrees left, 2 meters away" → `move_to_target_position(angle=45, distance=200)`
- "Stop" → `stop_move()`

---

## MCP Server: `go2-sport-state` — Robot State

Endpoint: `http://172.168.20.189:8001/sport_state/mcp`

Use this server to check the robot's current state before or after movement commands.

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_sport_mode_state` | none | Get robot state (default, uses echo) |
| `get_sport_mode_state_using_echo` | none | Get robot state via echo service |
| `get_sport_mode_state_using_ros2` | none | Get robot state via ROS2 node |

### State Data Returned

The `data` field contains a `SportModeState` object:

| Field | Type | Description |
|-------|------|-------------|
| `mode` | int | Sport mode (0=Idle, 1=Standing, 2=Walking_vel, 3=Walking_pos, 5=Stand_down, 6=Stand_up, 7=Damping, 8=Recovery) |
| `position` | float[3] | XYZ position in meters |
| `velocity` | float[3] | XYZ velocity |
| `yaw_speed` | float | Yaw rotation speed |
| `body_height` | float | Current body height |
| `foot_raise_height` | float | Foot raise height during walk |
| `foot_force` | int[4] | Force on each foot (4 legs) |
| `foot_position_body` | float[12] | Foot positions relative to body (3 per leg × 4 legs) |
| `foot_speed_body` | float[12] | Foot speeds relative to body |
| `imu_state.quaternion` | float[4] | Orientation quaternion |
| `imu_state.gyroscope` | float[3] | Angular velocity |
| `imu_state.accelerometer` | float[3] | Linear acceleration |
| `imu_state.rpy` | float[3] | Roll, Pitch, Yaw in radians |
| `imu_state.temperature` | int | IMU temperature |
| `gait_type` | int | Gait type (0=Idle, 1=Trot_walk, 2=Trot_run, 3=Stairs, 4=Trot_obstacle) |
| `range_obstacle` | float[4] | Obstacle distance in 4 directions |
| `error_code` | int | Error code (0 = no error) |

### Examples
- "What is the robot doing?" → `get_sport_mode_state()`
- "Check if the robot is standing" → `get_sport_mode_state()` then check `mode == 1`

---

## MCP Server: `go2-camera` — RPC Camera (Main Camera)

Endpoint: `http://172.168.20.189:8001/camera/mcp`

Use this for the robot's built-in main camera. Background capture runs at 30 FPS.

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `capture_image` | none | Capture the latest frame from the robot's main RPC camera |

Returns base64-encoded image in the `data` field.

---

## MCP Server: `go2-depth-camera` — Depth Camera

Endpoint: `http://172.168.20.189:8001/depth_camera/mcp`

Use this for depth/distance perception (Intel RealSense). Background capture runs at 30 FPS.

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `capture_image` | none | Capture the latest frame from the depth camera |

Returns base64-encoded image in the `data` field. May include YOLO detection and scene description in `extra_data`.

---

## MCP Server: `go2-local-camera` — Local Camera

Endpoint: `http://172.168.20.189:8001/local_camera/mcp`

Use this for the onboard USB/local camera. Background capture runs at 30 FPS.

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `capture_image` | none | Capture the latest frame from the local camera |

Returns base64-encoded image in the `data` field.

---

## MCP Server: `go2-speaker` — Speaker & TTS

Endpoint: `http://172.168.20.189:8001/speaker/mcp`

Use this server when the user wants the robot to speak, say something, play a sound, bark, or stop speaking.

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `speak_text` | `text: str`, `interrupt: bool` (default false) | Speak the given text aloud using TTS. Set interrupt=true to stop current audio first |
| `recorded_audio_speak` | `audio_name: str` (enum), `interrupt: bool` (default false) | Play a pre-recorded audio clip. Available: bark, happy, sad, alert, greeting, goodbye, acknowledge, error, confused |
| `stop_speaking` | none | Stop all currently playing audio immediately |

### Examples
- "Say hello" → `speak_text(text="Hello!")`
- "Bark!" → `recorded_audio_speak(audio_name="bark")`
- "Stop talking" → `stop_speaking()`
- "Say goodbye and wave" → `speak_text(text="Goodbye!")` then use go2-sport tools

---

## MCP Server: `go2-audio-capture` — Voice Capture (Hotword + ASR)

Endpoint: `http://172.168.20.189:8001/audio_capture/mcp`

Use this server when the user wants voice control—listen for hotword triggers and capture spoken commands via the microphone.

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_audio_tasks` | none | Get all voice tasks since last call. Each task is a command spoken after the hotword. Queue is drained on each call |
| `start_audio_background_capture` | none | Start background capture (hotword + ASR) |
| `stop_audio_background_capture` | none | Stop background capture |

Returns list of transcribed command strings in `data`. Use `GET /status` to check `audio_capture.available` before calling.

---

## Health Check

Verify the server is running: `GET http://172.168.20.189:8001/health`
Expected response: `{"message": "OK"}`

---

## Service Status

Check which hardware services are available: `GET http://172.168.20.189:8001/status`

Use this **before calling any MCP tool** to confirm the service is connected. If `available` is `false`, calling its tools returns `code=503`.

### Response

```json
{
  "status": "healthy | degraded",
  "summary": { "available": 3, "unavailable": 4, "unknown": 1 },
  "services": {
    "sport":         { "available": true,  "error": null,  "description": "Robot sport control (Unitree SDK)" },
    "rpc_camera":    { "available": false, "error": "...", "description": "Robot main camera (Unitree RPC)" },
    "depth_camera":  { "available": false, "error": "...", "description": "Intel RealSense depth camera" },
    "local_camera":  { "available": true,  "error": null,  "description": "Local webcam (OpenCV)" },
    "state_echo":    { "available": false, "error": "...", "description": "Robot state via ros2 topic echo" },
    "state_ros2":    { "available": false, "error": "...", "description": "Robot state via ROS2 subscriber node" },
    "speaker":       { "available": true,  "error": null,  "description": "Text-to-speech speaker" },
    "audio_capture": { "available": true,  "error": null,  "description": "Microphone voice capture (hotword + ASR)" }
  }
}
```

### `available` values

| Value | Meaning |
|-------|---------|
| `true` | Connected and ready |
| `false` | Failed to connect — check `error` field |
| `null` | Not yet initialized (transient at startup) |