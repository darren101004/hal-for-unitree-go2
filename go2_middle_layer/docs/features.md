# Features & API Reference

## 1. Overview

### 1.1 Service Description

The GO2 Middle Layer exposes **7 MCP (Model Context Protocol) services**, each mounted on its own path under a single FastAPI server. Every MCP tool returns a unified `Response` object.

#### 1.1.1 Unified Response Format

All endpoints return:

```json
{
  "success": true,
  "message": "Human-readable description of the result",
  "data": "<payload — varies by endpoint>",
  "code": 200,
  "extra_data": null
}
```

## 2. Sport Control — `/sport/mcp`

Controls the robot's movement and actions via the Unitree SDK2 sport client.

### 2.1 Tools

#### 2.1.1 `stop_move()`
Stops any current movement.

- **Input:** None
- **Output:** `Response` with a confirmation message

#### 2.1.2 `stand_up()`
Makes the robot stand up. It will automatically recover from the lying or damping state first.

- **Input:** None
- **Output:** `Response` with a confirmation message

#### 2.1.3 `stand_down()`
Makes the robot lie down. It will automatically transition through stand-up state if necessary.

- **Input:** None
- **Output:** `Response` with a confirmation message

#### 2.1.4 `move_forward(distance: int)`
Moves straight forward.

- **Input:** `distance` — distance in centimeters (clamped to `[0, 300]`)
- **Output:** `Response` with a message including the actual distance moved
- **Behavior:** Uses the depth camera to check for obstacles. Stops if an obstacle is detected closer than 400mm.

#### 2.1.5 `move_backward(distance: int)`
Moves straight backward.

- **Input:** `distance` — distance in centimeters (clamped to `[0, 300]`)
- **Output:** `Response` with a message including the actual distance moved

#### 2.1.6 `turn_left(angle: int)`
Turns left in place.

- **Input:** `angle` — angle in degrees (clamped to `[0, 180]`)
- **Output:** `Response` with a message including the actual degrees turned

#### 2.1.7 `turn_right(angle: int)`
Turns right in place.

- **Input:** `angle` — angle in degrees (clamped to `[0, 180]`)
- **Output:** `Response` with a message including the actual degrees turned

#### 2.1.8 `step_to_left(distance: int)`
Sidesteps to the left.

- **Input:** `distance` — distance in centimeters (clamped to `[0, 300]`)
- **Output:** `Response` with a message including the actual distance moved

#### 2.1.9 `step_to_right(distance: int)`
Sidesteps to the right.

- **Input:** `distance` — distance in centimeters (clamped to `[0, 300]`)
- **Output:** `Response` with a message including the actual distance moved

#### 2.1.10 `move_to_target_position(angle: float, distance: float)`
Turns to face a target direction and then walks forward to it, combining turning and forward movement in a single call.

- **Input:**
  - `angle` — angle in degrees (`[-180, 180]`). `0` = forward, positive = left, negative = right
  - `distance` — distance in centimeters (clamped to `[0, 300]`)
- **Output:** `Response` with a combined message for turn + move results
- **Behavior:** Uses the depth camera to check for obstacles during the forward phase.

### 2.2 Movement Policy Defaults

| Parameter            | Value      | Description                 |
|----------------------|------------|-----------------------------|
| `move_speed_mps`     | 0.4 m/s    | Linear movement speed       |
| `yaw_speed_rps`      | 0.5 rad/s  | Turning speed               |
| `loop_interval_sec`  | 0.01s      | Control loop interval       |
| `command_timeout_sec`| 3.0s       | SDK command timeout         |
| `retry_count`        | 1          | Retries on failed SDK command|

## 3. Sport State — `/sport_state/mcp`

Reads the robot's real-time state (position, velocity, IMU, foot force, etc.).

### 3.1 Tool: `get_sport_mode_state()`
Obtains the latest robot state.

- **Input:** None
- **Output:** `Response` where `data` is a `RobotState`:

```json
{
  "sportmodestate": {
    "stamp": { "sec": 1234567890, "nanosec": 123456789 },
    "error_code": 0,
    "imu_state": {
      "quaternion": [w, x, y, z],
      "gyroscope": [gx, gy, gz],
      "accelerometer": [ax, ay, az],
      "rpy": [roll, pitch, yaw],
      "temperature": 25
    },
    "mode": 1,
    "progress": 0.0,
    "gait_type": 1,
    "foot_raise_height": 0.08,
    "position": [x, y, z],
    "body_height": 0.3,
    "velocity": [vx, vy, vz],
    "yaw_speed": 0.0,
    "range_obstacle": [front, right, back, left],
    "foot_force": [fl, fr, rl, rr],
    "foot_position_body": [12 floats],
    "foot_speed_body": [12 floats]
  },
  "lowstate": { }
}
```
There are two implementations:

**`get_sport_mode_state_using_echo()`**: Reads state via a `ros2 topic echo` subprocess.
**`get_sport_mode_state_using_ros2()`**: Reads state using a native ROS2 subscriber node (rclpy), running in a separate process.

### 3.2 Sport Mode Values

| Value | Mode                |
|-------|---------------------|
| 0     | Idle                |
| 1     | Standing            |
| 2     | Walking (velocity)  |
| 3     | Walking (position)  |
| 4     | Walking (path)      |
| 5     | Stand down          |
| 6     | Stand up            |
| 7     | Damping             |
| 8     | Recovery            |
| 9     | Backflip            |
| 10    | Jump yaw            |
| 11    | Straight hand       |
| 12    | Dance 1             |
| 13    | Dance 2             |

### 3.3 Gait Type Values

| Value | Gait           |
|-------|----------------|
| 0     | Idle           |
| 1     | Trot walking   |
| 2     | Trot running   |
| 3     | Stairs climbing|
| 4     | Trot obstacle  |

---

## 4. RPC Camera — `/camera/mcp`

Captures images from the robot's built-in front camera via the Unitree SDK2 `VideoClient`.

**Tool: `capture_image()`**:
Gets the latest frame from the background capture buffer.
- **Input:** None
- **Output:** `Response` where `data` is a **base64-encoded PNG image** string
- **Error cases:**
  - `code: 425` — Buffer is empty, no frame has been captured yet
  - `code: 400` — Frame capture failed

---

## 5. Depth Camera — `/depth_camera/mcp`

Captures color and depth frames from an Intel RealSense camera, runs YOLO object detection, estimates 3D positions of detected objects, and generates a natural language scene description.

### 5.1 Tool: `capture_image()`
Gets the latest processed depth camera frame.

- **Input:** None
- **Output:** `Response` where:
  - `data` — base64-encoded JPEG image (color frame)
  - `extra_data` — rich analysis information:

```json
{
  "success": true,
  "message": "Successfully captured a frame from depth camera",
  "data": {
    "objects": [
      {
        "name": "person_1",
        "xyxyn": [0.1, 0.2, 0.5, 0.8],
        "xyxy": [128, 144, 640, 576],
        "distance_to_object": 1500,
        "coordinates": [x_mm, y_mm, z_mm]
      }
    ],
    "natural_language_description": "At 2026-03-03 14:30:00:\n1. person_1 at 150 centimeters, 15 degrees to the left of the center.\nNOTE: ..."
  }
}
```

### 5.2 Natural Language Description

The `natural_language_description` field provides an LLM-friendly textual summary of the scene:
- Timestamp of the capture
- Image caption (if captioner is enabled)
- For each detected close-range object: distance in centimeters and angle relative to center (left/right)
- Far-range objects (>6m) are listed by name
- Safety note about the limited field of view

### 5.3 Camera Configuration

| Parameter                  | Value         |
|----------------------------|--------------|
| Depth resolution           | 1280 x 720   |
| Color resolution           | 1280 x 720   |
| FPS                        | 30           |
| Far range threshold        | 6000 mm      |
| Obstacle avoidance threshold| 400 mm      |

---

## 6. Local Camera — `/local_camera/mcp`

Captures images from a locally connected camera (USB webcam or similar) using OpenCV.

### 6.1 Tool: `capture_image()`
Gets the latest frame from the background capture buffer.

- **Input:** None
- **Output:** `Response` where `data` is a **base64-encoded PNG image** string
- **Error cases:**
  - `code: 425` — Buffer is empty, no frame has been captured yet
  - `code: 400` — Frame capture failed

### 6.2 Camera Configuration

| Parameter  | Value         |
|------------|--------------|
| Resolution | 1280 x 720   |
| FPS        | 30           |
| Device ID  | Configurable via `LOCAL_CAMERA_DEVICE_ID` environment variable (default: `0`) |

---

## 7. Speaker — `/speaker/mcp`

Controls the robot's text-to-speech (TTS) engine and pre-recorded audio playback via the system speaker.

### 7.1 Tools

#### 7.1.1 `speak_text(text: str, interrupt: bool = False)`
Speak the given text out loud using TTS (text-to-speech). The robot will convert the text into speech and play it through its speaker.

- **Input:**
  - `text` — the text to speak
  - `interrupt` — if `True`, stop any currently playing audio before speaking (default: `False`)
- **Output:** `Response` with a confirmation message

#### 7.1.2 `recorded_audio_speak(audio_name: RecordedAudio, interrupt: bool = False)`
Play a pre-recorded audio clip through the robot's speaker.

- **Input:**
  - `audio_name` — one of: `bark`, `happy`, `sad`, `alert`, `greeting`, `goodbye`, `acknowledge`, `error`, `confused`
  - `interrupt` — if `True`, stop any currently playing audio before playing (default: `False`)
- **Output:** `Response` with a confirmation message
- **Error cases:**
  - Audio file not found — returns `success: false` with a message listing valid audio names

#### 7.1.3 `stop_speaking()`
Stop all currently playing audio immediately.

- **Input:** None
- **Output:** `Response` with a confirmation message

### 7.2 TTS Engine Configuration

The active TTS engine is selected via the `SPEAKER_TTS_ENGINE` environment variable:

| Engine | Value | Description |
|--------|-------|-------------|
| OpenAI TTS | `openai` (default) | Cloud-based, high-quality streaming TTS via OpenAI API |
| Piper TTS | `piper` | Offline, local TTS using ONNX models |

### 7.3 Speaker Configuration

| Parameter | Environment Variable | Default | Description |
|-----------|---------------------|---------|-------------|
| TTS Engine | `SPEAKER_TTS_ENGINE` | `openai` | TTS engine: `openai` or `piper` |
| Device ID | `SPEAKER_DEVICE_ID` | `None` (system default) | Audio output device ID |
| Sample Rate | `SPEAKER_SAMPLE_RATE` | `48000` | Output sample rate in Hz |
| Block Size | `SPEAKER_BLOCK_SIZE` | `1024` | Audio block size |
| Channels | `SPEAKER_CHANNELS` | `1` | Number of output channels |
| OpenAI API Key | `OPENAI_API_KEY` | `""` | API key for OpenAI TTS |
| OpenAI Base URL | `OPENAI_BASE_URL` | `None` | Custom OpenAI API base URL |
| TTS Model | `TTS_MODEL` | `gpt-4o-mini-tts` | OpenAI TTS model name |
| TTS Voice | `TTS_VOICE` | `coral` | OpenAI TTS voice name |
| Piper Model | `DEFAULT_PIPER_MODEL` | `en_US-lessac-medium.onnx` | Piper ONNX model file |
| Audio Directory | `SPEAKER_AUDIO_DIR` | `/opt/doggi/data/audio` | Directory containing pre-recorded `.wav` files |
| Chunk Write Timeout | `SPEAKER_CHUNK_WRITE_TIMEOUT` | `10.0` | Max seconds to wait for a single audio chunk write |
| Lock Acquire Timeout | `SPEAKER_LOCK_ACQUIRE_TIMEOUT` | `5.0` | Max seconds to wait for speaker lock |
| TTS Speed | `TTS_SPEED` | `1.5` | OpenAI TTS speech speed |
| TTS Chunk Size | `TTS_CHUNK_SIZE` | `2048` | PCM streaming chunk size in bytes |

### 7.4 Pre-recorded Audio Downloads

Pre-recorded WAV files for `recorded_audio_speak` can be downloaded using the provided script. The default directory is `resources/sound/dog` (relative to `src/`).

```bash
python scripts/download_recorded_audio.py
```

The script extracts **dog barks, growls, whimpers** from OpenGameArt's dog.7z pack (CC0). Requires `py7zr`. Use `--force` to replace, `--fallback` for direct WAV if py7zr unavailable. See `src/resources/sound/dog/SOURCES.md`.

---

## 8. Audio Capture — `/audio_capture/mcp`

Captures voice commands from the microphone using hotword detection and ASR. Supports two engines selectable via `AUDIO_CAPTURE_ENGINE`:

- **`vosk`** (default) — offline ASR using a local Vosk model. No API key required.
- **`deepgram`** — cloud ASR via Deepgram Flux streaming WebSocket. Requires `DEEPGRAM_API_KEY`.

Background capture listens for a hotword (e.g. "hello"), then transcribes the following speech into text tasks. Also supports transcribing external audio files (e.g. Telegram voice messages) without requiring a microphone.

### 8.1 Tools

#### 8.1.1 `get_audio_tasks()`
Return all voice tasks collected since the last call. Each task is a command spoken after the hotword or transcribed from external audio. The queue is drained on each call.

- **Input:** None
- **Output:** `Response` with `data` = list of transcribed command strings (empty list when no new tasks)
- **Error cases:**
  - Service unavailable — returns `success: false`, `code: 503` when audio capture is not available (no microphone, Vosk not installed, or device error)

#### 8.1.2 `transcribe_audio(audio_base64, audio_format)`
Transcribe an external audio file (e.g. Telegram voice message). Accepts base64-encoded audio data and a format hint. Transcribed text is returned immediately and also appended to the task queue (retrievable via `get_audio_tasks`). Does not require a microphone — only the Vosk model.

- **Input:**
  - `audio_base64` (str, required) — base64-encoded audio file bytes
  - `audio_format` (str, default `"ogg"`) — audio format hint (ogg, wav, mp3, flac, webm)
- **Output:** `Response` with `data` = list of transcribed sentence strings
- **Error cases:**
  - Bad format or decode error — returns `success: false`, `code: 400`
- **Dependencies:** `pydub` (Python) + `ffmpeg` (system binary)

#### 8.1.3 `start_audio_background_capture()`
Start the background audio capture loop (hotword detection + ASR).

- **Input:** None
- **Output:** `None` (no Response; starts the capture thread)
- **Threading model:** Hotword callbacks are executed in **daemon worker threads** so the hotword loop remains responsive while a command session is being transcribed.

#### 8.1.4 `stop_audio_background_capture()`
Stop the background audio capture loop.

- **Input:** None
- **Output:** `None` (no Response; stops the capture thread)

### 8.2 Audio Capture Configuration

| Parameter | Environment Variable | Default | Description |
|-----------|---------------------|---------|-------------|
| Engine | `AUDIO_CAPTURE_ENGINE` | `vosk` | ASR engine: `vosk` (offline) or `deepgram` (cloud) |
| Device ID | `AUDIO_CAPTURE_DEVICE_ID` | `None` | Microphone device ID (system default if unset) |
| Hotwords | `AUDIO_CAPTURE_HOTWORDS` | `hello` | Comma-separated hotword(s) to trigger listening |
| Patience | `AUDIO_CAPTURE_PATIENCE` | `3` | Seconds of silence before ending a command session |
| ASR Model | `AUDIO_CAPTURE_MODEL_ID` | `vosk-model-small-en-us-0.15` | Vosk ASR model name (vosk engine only) |
| Sample Rate | `AUDIO_CAPTURE_SAMPLE_RATE` | `16000` | Microphone sample rate in Hz |
| Channels | `AUDIO_CAPTURE_CHANNELS` | `1` | Microphone channel count |
| Silence Threshold | `AUDIO_CAPTURE_SILENCE_THRESHOLD` | `0.01` | RMS silence threshold, normalized [-1,1] |
| Deepgram API Key | `DEEPGRAM_API_KEY` | `""` | Deepgram API key (deepgram engine only) |
| Deepgram Model | `DEEPGRAM_MODEL` | `flux-general-en` | Deepgram model name (deepgram engine only) |

### 8.3 Service Availability

If the required dependencies are unavailable (`sounddevice`/`vosk` for vosk engine, `sounddevice`/`deepgram` for deepgram engine), or the microphone fails, the service registers as unavailable. `get_audio_tasks` then returns `code: 503`. Check `GET /status` for `audio_capture.available`.

---

## 9. Health Check — `/health`

A simple HTTP GET endpoint (not an MCP tool).

- **Method:** `GET`
- **Output:** `{"message": "OK"}`

---

## 10. Service Status — `/status`

Returns the availability of all hardware services. Use this to check which services are connected before calling their APIs.

- **Method:** `GET`
- **Output:**

```json
{
  "status": "healthy | degraded",
  "summary": { "available": 3, "unavailable": 4, "unknown": 1 },
  "services": {
    "sport":         { "available": true,  "error": null,    "description": "Robot sport control (Unitree SDK)" },
    "rpc_camera":    { "available": false, "error": "...",   "description": "Robot main camera (Unitree RPC)" },
    "depth_camera":  { "available": false, "error": "...",   "description": "Intel RealSense depth camera" },
    "local_camera":  { "available": true,  "error": null,    "description": "Local webcam (OpenCV)" },
    "state_echo":    { "available": false, "error": "...",   "description": "Robot state via ros2 topic echo" },
    "state_ros2":    { "available": false, "error": "...",   "description": "Robot state via ROS2 subscriber node" },
    "speaker":       { "available": true,  "error": null,    "description": "Text-to-speech speaker" },
    "audio_capture": { "available": true,  "error": null,    "description": "Microphone voice capture (hotword + ASR)" }
  }
}
```

**`available` values:**
- `true` — service started and connected
- `false` — service failed to connect (`error` contains the reason)
- `null` — service not yet initialized (transient, should resolve after startup)

**When a service is unavailable**, calling its MCP tools returns `Response(success=false, code=503, message="... not available: <reason>")` instead of crashing.

---

## 11. Device Watcher — Auto-Recovery

The Device Watcher monitors all hardware services and automatically restarts them when they fail (USB cable disconnected, process crash, device timeout, or robot not booted yet). It runs a single background polling thread that periodically checks each service's health.

### 11.1 Behavior

- **Health check:** Every `DEVICE_WATCHER_POLL_INTERVAL` seconds, the watcher calls `is_healthy()` on each registered service
- **Recovery:** When a service is detected as unhealthy, the watcher calls `restart()` (stop + start) with exponential backoff
- **Backoff:** Starts at `DEVICE_WATCHER_BASE_BACKOFF` seconds, doubles each retry, capped at `DEVICE_WATCHER_MAX_BACKOFF`
- **Initial connect vs runtime recovery:** The watcher tracks whether each service has **ever been healthy**. Services that have never been healthy (e.g. robot not booted when the server started) retry with **unlimited attempts** until they connect successfully. Services that were previously healthy but later failed respect the `DEVICE_WATCHER_MAX_RETRIES` limit.
- **Grace period:** The watcher waits `DEVICE_WATCHER_INITIAL_GRACE_PERIOD` seconds after starting before the first health check, giving services time to initialize
- **Stub skip:** Stub services (used when hardware dependencies are not installed) are not watched

### 11.2 Watched Services

| Service | Health Check | Recovery Action |
|---------|-------------|-----------------|
| sport | SDK client initialized and available | Re-initialize ChannelFactory, recreate SportClient, rebuild API mapping |
| depth_camera | Thread alive + pipeline active | Stop pipeline, re-initialize RealSense, restart thread |
| local_camera | Thread alive | Release VideoCapture, reopen device, restart thread |
| rpc_camera | Thread alive | Re-initialize Unitree VideoClient, restart thread |
| state_ros2 | Process alive + reader thread alive | Kill subprocess, drain queue, cleanup semaphores, restart |
| audio_capture | Thread alive | Stop device, restart capture thread |
| speaker | Audio stream active | Reset OutputStream (abort + recreate) |

### 11.3 Configuration

| Parameter | Environment Variable | Default | Description |
|-----------|---------------------|---------|-------------|
| Enabled | `DEVICE_WATCHER_ENABLED` | `true` | Enable/disable the device watcher |
| Poll Interval | `DEVICE_WATCHER_POLL_INTERVAL` | `5.0` | Seconds between health checks |
| Base Backoff | `DEVICE_WATCHER_BASE_BACKOFF` | `2.0` | Base retry delay in seconds |
| Max Backoff | `DEVICE_WATCHER_MAX_BACKOFF` | `120.0` | Maximum retry delay cap in seconds |
| Max Retries | `DEVICE_WATCHER_MAX_RETRIES` | `5` | Max restart attempts for runtime failures (0 = unlimited). Initial connect is always unlimited. |
| Grace Period | `DEVICE_WATCHER_INITIAL_GRACE_PERIOD` | `10.0` | Wait before first health check |

### 11.4 Status

The `/status` endpoint includes a `device_watcher` section showing the state of each watched service:

```json
{
  "device_watcher": {
    "sport": { "state": "healthy", "retry_count": 0, "max_retries": 5, "ever_healthy": true },
    "rpc_camera": { "state": "recovering", "retry_count": 8, "max_retries": 5, "ever_healthy": false },
    "local_camera": { "state": "recovering", "retry_count": 2, "max_retries": 5, "ever_healthy": true }
  }
}
```

States: `healthy` (operating normally), `recovering` (restart attempts in progress), `failed` (gave up after max retries — only for services that were previously healthy).

The `ever_healthy` field indicates whether the service has ever successfully connected. When `false`, the watcher retries indefinitely (initial connect mode).

---

## 12. DL Backend — Object Detection Server

A self-contained FastAPI server (`dlbackend/`) providing zero-shot object detection via **YOLO-World** and **Grounding DINO**. Serves as the detection backend for the depth camera pipeline.

### 12.1 Endpoints

All endpoints are under the `/api/dl` prefix.

#### 12.1.1 `POST /api/dl/yoloworld`

Run YOLO-World zero-shot detection using ultralytics.

- **Input:** `DetectionRequest` (JSON)
  - `image_b64` (str, required) — base64-encoded JPEG or PNG image
  - `classes` (list[str], optional) — object classes to detect. If omitted, ~400 default classes are used.
- **Output:** JSON array of `DetectionResult`:
```json
[
  { "class_name": "person", "xywh": [320.5, 240.0, 80.0, 160.0], "confidence": 0.92 }
]
```
- `xywh`: `[center_x, center_y, width, height]` in pixel coordinates
- `confidence`: detection confidence score

#### 12.1.2 `POST /api/dl/grounding-dino`

Run Grounding DINO zero-shot detection using HuggingFace transformers. Same request/response format as YOLO-World.

#### 12.1.3 `GET /api/dl/health`

Health check returning model availability.

```json
{
  "status": "ok",
  "yolo_world": true,
  "grounding_dino": true
}
```

### 12.2 Configuration

Models are configured via `dlbackend/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `YOLO_WORLD_MODEL` | `yolov8x-worldv2.pt` | YOLO-World model variant |
| `GROUNDING_DINO_MODEL` | `IDEA-Research/grounding-dino-tiny` | Grounding DINO HuggingFace model ID |

### 12.3 Default Classes

When `classes` is omitted from the request, ~400 default classes are used, covering:

| Category | Count | Examples |
|----------|-------|---------|
| Indoor objects | 100 | chair, table, refrigerator, lamp, toilet |
| Outdoor objects | 100 | car, traffic light, fire hydrant, bench, fence |
| Natural objects | 100 | eagle, butterfly, oak tree, mushroom, waterfall |
| General objects | 100 | animal, food, clothing, tool, guitar, drone |

### 12.4 Deployment

The DL backend runs on a separate GPU server. See `dlbackend/README.md` for setup instructions, Docker deployment, and RunPod/nginx configuration.

To integrate with the GO2 middle layer, set `DEFAULT_REMOTE_DETECTOR_URL` in the main `.env`:

```env
DEFAULT_REMOTE_DETECTOR_URL=https://<host>/api/dl/yoloworld
```