# Architecture
## 1. Folder Structure

```
src/
├── server.py                          # FastAPI app, mounts all MCP sub-apps, manages lifespan
├── requirements.txt                   # Python dependencies
│
├── dependencies/
│   └── __init__.py                    # DI container (Go2MiddleLayerContainer), ServiceSettings
│
├── interfaces/
│   ├── audio.py                       # AudioCaptureService ABC
│   ├── camera.py                      # CameraService ABC
│   ├── speaker.py                     # SpeakerService ABC
│   ├── sport.py                       # SportService ABC
│   └── state.py                       # StateService ABC
│
├── impl/
│   ├── sdk_sport_service.py           # SportService → Unitree SDK2 SportClient
│   ├── echo_state_service.py          # StateService → ros2 topic echo subprocess
│   ├── ros2_state_service.py          # StateService → rclpy subscriber (separate process)
│   ├── sdk_state_service.py           # StateService → rclpy subscriber (same process thread)
│   ├── rpc_camera_service.py          # CameraService → Unitree SDK2 VideoClient
│   ├── depth_camera_service.py        # CameraService → Intel RealSense pyrealsense2
│   ├── local_camera_service.py        # CameraService → OpenCV VideoCapture
│   ├── utils.py                       # 3D position estimation, depth processing, NL description
│   ├── audio_capture/                 # Audio capture implementations
│   │   ├── __init__.py
│   │   ├── audio_capture_device.py    # Microphone device, hotword detection, Vosk ASR
│   │   ├── service.py                 # AudioCaptureServiceImpl (background thread)
│   │   └── service_stub.py            # AudioCaptureServiceStub (no-op when no mic/vosk)
│   └── speaker/                       # Speaker/TTS implementations
│       ├── __init__.py
│       ├── base.py                    # SpeakerDeviceBase, SyncSpeakerDeviceBase, AsyncSpeakerDeviceBase
│       ├── models.py                  # RecordedAudio enum, SpeakerDeviceInfo, SupportedLanguages
│       ├── tts.py                     # TTS engines: openai_tts_realtime, piper_tts_realtime, Resampler
│       ├── openai_speaker_service.py  # SpeakerService → OpenAI TTS API (streaming)
│       └── piper_speaker_service.py   # SpeakerService → Piper TTS (offline, local)
│
├── mcps/
│   ├── configs.py                     # Settings, logging setup
│   ├── sport.py                       # MCP tools for sport control
│   ├── sportstate.py                  # MCP tools for state reading
│   ├── rpc_camera.py                  # MCP tools for robot camera
│   ├── depth_camera.py                # MCP tools for depth camera
│   ├── local_camera.py               # MCP tools for local camera
│   ├── speaker.py                    # MCP tools for speaker/TTS
│   └── audio_capture.py              # MCP tools for audio capture/ASR
│
├── usecases/
│   ├── sport_controller.py            # Movement orchestration, obstacle avoidance
│   ├── state_controller.py            # State service routing
│   ├── rpc_camera_controller.py       # RPC camera response formatting
│   ├── depth_camera_controller.py     # Depth camera response formatting
│   ├── local_camera_controller.py     # Local camera response formatting
│   ├── speaker_controller.py         # Speaker TTS orchestration, recorded audio lookup
│   └── audio_capture_controller.py    # Audio capture task retrieval, transcription
│
├── models/
│   ├── response.py                    # Unified Response model
│   ├── sport_request.py               # SportRequest, SportHandler
│   ├── sport_option.py                # SportOption enum, API ID mapping, response codes
│   └── state.py                       # RobotState, SportModeStateDict, IMUStateDict, enums
│
└── utils/
    ├── captioning.py                  # Captioner ABC, RemoteCaptioner
    └── yolov8/
        ├── base.py                    # ObjectDetector ABC, default class list
        ├── yolov8_detector.py         # Local YOLOv8 detector (ultralytics)
        └── yolov8_remote_detector.py  # Remote YOLO detector (HTTP API)
```

## 2. High-Level Overview

The GO2 Middle Layer is a **FastAPI server** that wraps the Unitree GO2 robot's low-level SDK, ROS2, and hardware interfaces behind a set of **MCP (Model Context Protocol)** endpoints. This allows AI agents (LLMs) to control the robot and perceive its environment through simple tool calls over HTTP.

```
┌─────────────────────────────────────────────────────────────┐
│                      AI Agent / LLM                         │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP (MCP over Streamable HTTP)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Server (server.py)               │
│                                                             │
│  ┌──────────┐ ┌───────────┐ ┌────────┐  ┌───────┐ ┌──────┐  │
│  ┌──────────┐ ┌───────────┐ ┌────────┐  ┌───────┐ ┌──────┐ ┌───────┐ ┌───────┐│
│  │/sport/mcp│ │/sport_    │ │/camera/│  │/depth_│ │/local│ │/speak-│ │/audio_││
│  │          │ │ state/mcp │ │  mcp   │  │camera/│ │_cam/ │ │er/mcp │ │capture││
│  │          │ │           │ │        │  │  mcp  │ │ mcp  │ │       │ │/mcp   ││
│  └────┬─────┘ └─────┬─────┘ └───┬────┘  └───┬───┘ └──┬───┘ └──┬────┘ └──┬────┘│
│       │             │           │           │        │        │        │     │
│  ┌────▼─────────────▼───────────▼───────────▼────────▼────────▼────────▼──┐  │
│  │              MCP Layer (mcps/*.py)                                     │  │
│  │  FastMCP tool definitions + background start/stop                      │  │
│  └────┬─────────────┬───────────┬───────────┬────────┬────────┬────────┬──┘  │
│       │             │           │           │        │        │        │     │
│  ┌────▼─────────────▼───────────▼───────────▼────────▼────────▼────────▼──┐  │
│  │           Use Case Layer (usecases/*.py)                               │  │
│  │  SportController, StateController, RpcCameraController,                │  │
│  │  DepthCameraController, LocalCameraController,                         │  │
│  │  SpeakerController, AudioCaptureController                             │  │
│  └────┬─────────────┬───────────┬───────────┬────────┬────────┬────────┬──┘  │
│       │             │           │           │        │        │        │     │
│  ┌────▼─────────────▼───────────▼───────────▼────────▼────────▼────────▼──┐  │
│  │          Interface Layer (interfaces/*.py)                             │  │
│  │  SportService (ABC), StateService (ABC), CameraService (ABC),          │  │
│  │  SpeakerService (ABC), AudioCaptureService (ABC)                       │  │
│  └────┬─────────────┬───────────┬───────────┬────────┬────────┬────────┬──┘  │
│       │             │           │           │        │        │        │     │
│  ┌────▼─────────────▼───────────▼───────────▼────────▼────────▼────────▼──┐  │
│  │        Implementation Layer (impl/*.py)                                │  │
│  │  SdkSportService, Ros2EchoSportStateService, Ros2SportStateService,    │  │
│  │  RpcCameraService, DepthCameraService, LocalCameraService,             │  │
│  │  OpenAISpeakerService, PiperSpeakerService, AudioCaptureServiceImpl    │  │
│  └────┬─────────────┬───────────┬───────────┬────────┬────────┬────────┬──┘  │
└───────┼─────────────┼───────────┼───────────┼────────┼──────┘
        │             │           │           │        │
        ▼             ▼           ▼           ▼        ▼
  ┌──────────┐  ┌──────────┐ ┌────────┐ ┌─────────┐ ┌──────┐
  │Unitree   │  │ROS2/DDS  │ │Unitree │ │Intel    │ │OpenCV│
  │SDK2      │  │(rclpy /  │ │SDK2    │ │RealSense│ │(USB  │
  │SportClient│ │ros2 echo)│ │Video   │ │(pyreal- │ │cam)  │
  └──────────┘  └──────────┘ │Client  │ │sense2)  │ └──────┘
                             └────────┘ └─────────┘
```

## 3. Layered Architecture

The codebase follows a **4-layer architecture** with clear separation of concerns:

### 3.1. Layer 1: MCP Layer (`mcps/*.py`)

**Role:** Define MCP tools (the "API surface") and manage background service lifecycle.

Each file declares a `FastMCP` instance and registers tools using the `@mcp.tool()` decorator. This layer is thin — it only:
- Defines the MCP tool signatures and descriptions
- Delegates to the corresponding use case controller
- Exposes `start_*` / `stop_*` functions called by `server.py` during app lifespan

**Files:**
| File | FastMCP name | Mount path |
|---|---|---|
| `mcps/sport.py` | `"sport"` | `/sport/mcp` |
| `mcps/sportstate.py` | `"state"` | `/sport_state/mcp` |
| `mcps/rpc_camera.py` | `"camera"` | `/camera/mcp` |
| `mcps/depth_camera.py` | `"depth_camera"` | `/depth_camera/mcp` |
| `mcps/local_camera.py` | `"local_camera"` | `/local_camera/mcp` |
| `mcps/speaker.py` | `"speaker"` | `/speaker/mcp` |
| `mcps/audio_capture.py` | `"audio_capture"` | `/audio_capture/mcp` |

### 3.2. Layer 2: Use Case Layer (`usecases/*.py`) - Controllers

**Role:** Orchestrate business logic. Controllers coordinate between multiple services to fulfill a single user intent.

Key behaviors implemented here (not in services):
- **`SportController`**: Manages movement commands with async locking (only one movement at a time), cancellation of in-progress commands, automatic stand-up before moving, obstacle avoidance using depth camera during forward movement, and duration-based velocity control loops.
- **`StateController`**: Routes state requests to the correct implementation (echo vs ros2), manages lifecycle of both state services.
- **`RpcCameraController` / `DepthCameraController` / `LocalCameraController`**: Convert raw frames from services into base64-encoded `Response` objects.
- **`SpeakerController`**: Delegates TTS requests to the active `SpeakerService`, resolves pre-recorded audio file paths from enum values, and handles speaker interruption.
- **`AudioCaptureController`**: Drains pending voice tasks from `AudioCaptureService`, transcribes external audio data, and manages background capture lifecycle. Checks service availability via `service_registry` before calling the service.

Dependencies are injected into controller methods via `@inject` + `Provide[...]` decorators from `dependency-injector`.

### 3.3. Layer 3: Interface Layer (`interfaces/*.py`) 

**Role:** Define abstract contracts (ABCs) that implementations must fulfill. This decouples the use case layer from specific implementations.

```
interfaces/
├── sport.py    → SportService(ABC):  handle(SportRequest) → Response
├── state.py    → StateService(ABC):  start(), stop(), get_latest_state()
├── camera.py   → CameraService(ABC): start(fps), stop(), get_latest_frame()
├── speaker.py  → SpeakerService(ABC): speak(), aspeak(), play_file(), aplay_file(), interrupt_all_task()
└── audio.py    → AudioCaptureService(ABC): start(), stop(), get_pending_tasks(), transcribe_audio()
```

`StateService`, `CameraService`, and `AudioCaptureService` follow a **background service pattern**: `start()` spawns a background thread/process that continuously updates an internal buffer, and `get_latest_state()`/`get_latest_frame()` reads from that buffer.

### 3.4. Layer 4: Implementation Layer (`impl/*.py`) - Services Implementation

**Role:** Concrete implementations that interact with hardware, SDK, and external services.

| Implementation | Interface | Communication Method |
|---|---|---|
| `SdkSportService` | `SportService` | Unitree SDK2 `SportClient` over DDS |
| `Ros2EchoSportStateService` | `StateService` | `ros2 topic echo` subprocess + YAML parsing |
| `Ros2SportStateService` | `StateService` | `rclpy` subscriber in a separate process, communicating via `multiprocessing.Queue` |
| `SDKSubscriberSportStateService` | `StateService` | `rclpy` subscriber in a background thread (same process) |
| `RpcCameraService` | `CameraService` | Unitree SDK2 `VideoClient` over DDS |
| `DepthCameraService` | `CameraService` | Intel RealSense `pyrealsense2` pipeline |
| `LocalCameraService` | `CameraService` | OpenCV `VideoCapture` |
| `OpenAISpeakerService` | `SpeakerService` | OpenAI TTS API (async streaming via `sounddevice`) |
| `PiperSpeakerService` | `SpeakerService` | Piper TTS engine (offline, local via `sounddevice`) |
| `AudioCaptureServiceImpl` | `AudioCaptureService` | Vosk ASR + `sounddevice` microphone input, hotword detection |

---

## 4. Dependency Injection

The project uses **`dependency-injector`** for wiring services together. This is centralized in `dependencies/__init__.py`.

### 4.1. Container: `Go2MiddleLayerContainer`

```
Go2MiddleLayerContainer
├── config (Configuration)
│
├── sport_service          → SdkSportService (Singleton)
│
├── state_service_using_echo  → Ros2EchoSportStateService (Singleton)
│                               config: topic
│
├── state_service_using_ros2  → Ros2SportStateService (Singleton)
│                               config: topic
│
├── rpc_camera_service     → RpcCameraService (Singleton)
│                            config: network_interface
│
├── depth_camera_service   → DepthCameraService (Singleton)
│                            config: fps, remote_detector_url
│
├── local_camera_service   → LocalCameraService (Singleton)
│                            config: device_id
│
├── speaker_service_openai → OpenAISpeakerService (Singleton)
│                            config: device_id, sample_rate, block_size, channels,
│                                    api_key, base_url, tts_model, tts_voice
│
├── speaker_service_piper  → PiperSpeakerService (Singleton)
│                            config: device_id, sample_rate, block_size, channels,
│                                    piper_model
│
├── speaker_service        → Selector(tts_engine: openai | piper)
│
└── audio_capture_service  → AudioCaptureServiceImpl (Singleton)
                             config: device_id, hotwords, patience,
                                     model_id, sample_rate, channels
```

### 4.2. Configuration Flow

```
Environment / .env file
        │
        ▼
  ServiceSettings (pydantic-settings)
        │
        ▼
  Go2MiddleLayerContainer.config.from_dict({...})
        │
        ▼
  Each service receives its config at construction
```

### 4.3. Wiring

At application startup (`server.py`), the container is wired to the following modules so that `@inject` + `Provide[...]` decorators work:

```python
container.wire(modules=[
    "mcps.rpc_camera",
    "mcps.depth_camera",
    "mcps.local_camera",
    "mcps.sport",
    "mcps.sportstate",
    "mcps.speaker",
    "mcps.audio_capture",
    "usecases",
    "usecases.speaker_controller",
    "usecases.audio_capture_controller",
    "interfaces",
    "impl",
    "impl.speaker",
    "impl.audio_capture",
])
```

When a controller method is called, `dependency-injector` automatically resolves `Provide[Go2MiddleLayerContainer.some_service]` to the singleton instance.

### 4.4. Service Stubs (Bypass Mode)

Optional services use **stub implementations** when their dependencies are missing. This allows the server to run on any machine without the GO2 robot, RealSense, ROS2, etc.

| Service | Real Implementation | Stub | Trigger |
|---------|---------------------|------|---------|
| Depth camera | `DepthCameraService` | `DepthCameraServiceStub` | `pyrealsense2` not installed |
| ROS2 state | `Ros2SportStateService` | `Ros2SportStateServiceStub` | `rclpy` not installed |
| RPC camera | `RpcCameraService` | `RpcCameraServiceStub` | `unitree_sdk2py` not installed |
| Sport | `SdkSportService` | `SdkSportServiceStub` | `unitree_sdk2py` not installed |
| Audio capture | `AudioCaptureServiceImpl` | `AudioCaptureServiceStub` | `sounddevice`/`vosk` not installed or mic device fails |

Stubs are selected in `dependencies/__init__.py` via `try/except ImportError`. See `docs/DEVELOPMENT.md` for full context.

---

## 5. Background Service Pattern

All camera and state services follow the same pattern:

```
┌─────────────────────────────────────┐
│          Background Thread          │
│                                     │
│  while not stop_event:              │
│    frame = read_from_hardware()     │
│    with lock:                       │
│      buffer = frame                 │
│    sleep(1/fps)                     │
│                                     │
└───────────────┬─────────────────────┘
                │ writes to
                ▼
        ┌──────────────┐
        │   Buffer     │ ← protected by threading.Lock
        │ (latest      │
        │  frame/state)│
        └──────┬───────┘
               │ reads from
               ▼
┌──────────────────────────────┐
│     MCP Tool Handler         │
│                              │
│  with lock:                  │
│    return buffer             │
└──────────────────────────────┘
```

This ensures:
- MCP tool calls return instantly (no I/O wait)
- The latest data is always available
- Thread-safe access to shared buffer

### 5.1. Service Lifecycle

All background services are managed in `server.py` via FastAPI's lifespan context manager:

```
App Startup (combined_lifespan)
│
├── wire_container()           ← Initialize DI
├── start_state_background_reader()
├── start_rpc_camera_background_capture(fps=30)
├── start_depth_camera_background_capture(fps=30)
├── start_local_camera_background_capture(fps=30)
├── start_audio_background_capture()
├── Enter lifespan for each MCP sub-app
│
│   ... server is running ...
│
App Shutdown (finally) — LIFO order, graceful shutdown
├── stop_audio_background_capture()
├── stop_local_camera_background_capture()
├── stop_depth_camera_background_capture()
├── stop_rpc_camera_background_capture()
└── stop_state_background_reader()
```

Port fallback: if the requested port is in use, the server tries the next port (up to 10 attempts). Use `--no-port-fallback` to disable.

---

## 6. Sport Controller: Movement Logic

The `SportController` is the most complex use case. It implements a velocity-based control loop for precise distance/angle movements.

### 6.1. Movement Flow

```
MCP tool call (e.g. move_forward(100))
│
├── Cancel any in-progress command (_cancel_current_command)
├── Acquire async lock (only one movement at a time)
├── Ensure robot is standing (_ensure_standing_async)
│   ├── Read current mode from StateService
│   └── Send RecoveryStand / BalanceStand if needed
│
├── Calculate duration = distance / speed
├── Run move loop (_run_move_loop):
│   │
│   │  while elapsed < duration:
│   │    ├── Check cancel event (new command arrived?)
│   │    ├── Check obstacle distance via DepthCameraService (forward only)
│   │    ├── Send Move(vx, vy, vyaw) to SportService
│   │    └── sleep(loop_interval)
│   │
│   └── Send StopMove
│
└── Return Response with actual distance/angle moved
```

### 6.2. Command Cancellation

When a new movement command arrives while one is in progress:
1. The new command sets `_cancel_event`
2. The running loop detects the event and exits early
3. The new command acquires the lock and starts its own loop

This prevents conflicting movement commands from being sent simultaneously.

---

## 7. Depth Camera Pipeline

The depth camera service has the most complex data processing pipeline:

```
Intel RealSense Camera
│
├── Depth Stream (1280x720, Z16, 30fps)
├── Color Stream (1280x720, BGR8, 30fps)
│
▼ (background thread)
Buffer: latest composite_frame
│
▼ (on MCP tool call)
│
├── 1. Align depth to color frame
├── 2. Run YOLO detection on color image (remote HTTP call)
├── 3. Run captioning on color image (optional, remote HTTP call)
│      (steps 1-3 run in parallel via asyncio.gather)
│
├── 4. For each detected object:
│   ├── Extract bounding box from normalized coordinates
│   ├── Compute depth within bounding box (box filter + min sampling)
│   ├── Filter far objects (> 6000mm)
│   └── Estimate 3D position using camera intrinsics
│       (compensate 35mm X-axis offset)
│
├── 5. Sort objects by distance, add unique name suffixes
├── 6. Generate natural language description
├── 7. Encode color image as JPEG
│
└── Return (info_dict, image_bytes)
```

**Remote Services Used**

| Service | URL (default) | Purpose |
|---|---|---|
| YOLO World Detector | `http://<host>:8000/api/dl/yoloworld` | Object detection with open-vocabulary classes |
| Grounding DINO Detector | `http://<host>:8000/api/dl/grounding-dino` | Zero-shot object detection with text prompts |
| Remote Captioner | `http://14.225.217.119:8182/oai-caption` | Image captioning (currently disabled in code) |

The YOLO World and Grounding DINO detectors are served by the **DL Backend** (`dlbackend/`), a self-contained FastAPI service. See [DL Backend](#10-dl-backend) for details.

---

## 8. State Service: Two Implementations

The project provides two mechanisms to read robot state, both running simultaneously:

### 8.1. Echo Implementation (`Ros2EchoSportStateService`)

```
Background Thread
│
├── Spawn: ros2 topic echo /lf/sportmodestate --qos-reliability best_effort
├── Read stdout line by line
├── Collect lines until "---" separator
├── Parse YAML block → RobotState.sportmodestate
└── Store in buffer
```

**Pros:** No rclpy dependency in the main process. Simple subprocess approach.
**Cons:** Slower, depends on `ros2` CLI being available.

### 8.2. ROS2 Node Implementation (`Ros2SportStateService`)

```
Main Process                    Separate Process
│                               │
├── mp.Queue ◄─── state ──── ROS2 Subscriber Node
├── mp.Event (stop signal)      │
│                               ├── rclpy.init()
├── Reader Thread               ├── Create SportStateSubscriber
│   └── queue.get() → buffer    ├── executor.spin()
│                               └── On message: queue.put(state)
```

**Pros:** Native ROS2 subscriber, lower latency, more reliable.
**Cons:** Requires rclpy and ROS2 message types in a separate process to avoid GIL issues.

Both services are started at application startup. The sport controller uses `state_service_using_ros2` for real-time mode checks, while the MCP tools expose both options.

---

## 9. Speaker Service: TTS & Audio Playback

The speaker service enables the robot to speak text aloud and play pre-recorded audio clips.

### 9.1. Architecture

```
MCP tool call (e.g. speak_text("Hello"))
│
├── SpeakerController.speak_text(text, interrupt)
│   └── SpeakerService.aspeak(text, interrupt)
│       ├── TTS engine generates audio chunks (streaming)
│       ├── Resampler converts to output sample rate
│       └── sounddevice.OutputStream plays audio
│
├── SpeakerController.play_recorded_audio(audio_name, interrupt)
│   ├── Resolve file path: {SPEAKER_AUDIO_DIR}/{audio_name}.wav
│   └── SpeakerService.aplay_file(file_path, interrupt)
│       ├── soundfile reads WAV file in chunks
│       ├── Resampler converts to output sample rate
│       └── sounddevice.OutputStream plays audio
│
└── SpeakerController.interrupt()
    └── SpeakerService.interrupt_all_task()
```

### 9.2. Two TTS Implementations

| Implementation | Base Class | TTS Engine | Use Case |
|---|---|---|---|
| `OpenAISpeakerService` | `AsyncSpeakerDeviceBase` | OpenAI TTS API (streaming) | High-quality, cloud-based TTS |
| `PiperSpeakerService` | `SyncSpeakerDeviceBase` | Piper (local ONNX model) | Offline, low-latency TTS |

The active implementation is selected via the `SPEAKER_TTS_ENGINE` environment variable (`openai` or `piper`), using `dependency-injector`'s `Selector` provider.

### 9.3. Audio Pipeline

```
TTS Engine (24kHz mono)
│
├── Resampler (soxr): 24kHz → 48kHz (output sample rate)
├── _normalize_audio: scale to float32 range
├── _adapt_channels: match stream channel count (mono ↔ stereo)
│
└── sounddevice.OutputStream.write(chunk)
```

### 9.4. Pre-recorded Audio (RecordedAudio Enum)

Available audio clips are defined as a `RecordedAudio` enum:

| Value | File |
|---|---|
| `bark` | `{SPEAKER_AUDIO_DIR}/bark.wav` |
| `happy` | `{SPEAKER_AUDIO_DIR}/happy.wav` |
| `sad` | `{SPEAKER_AUDIO_DIR}/sad.wav` |
| `alert` | `{SPEAKER_AUDIO_DIR}/alert.wav` |
| `greeting` | `{SPEAKER_AUDIO_DIR}/greeting.wav` |
| `goodbye` | `{SPEAKER_AUDIO_DIR}/goodbye.wav` |
| `acknowledge` | `{SPEAKER_AUDIO_DIR}/acknowledge.wav` |
| `error` | `{SPEAKER_AUDIO_DIR}/error.wav` |
| `confused` | `{SPEAKER_AUDIO_DIR}/confused.wav` |

**Download script:** Run `python scripts/download_recorded_audio.py` to fetch dog bark WAV files from OpenGameArt.org. See `docs/features.md` §7.4 and `src/resources/sound/dog/SOURCES.md`.

---

## 10. DL Backend (Object Detection Server)

The `dlbackend/` directory contains a **self-contained FastAPI server** for zero-shot object detection, designed to replace the external detection server used by the depth camera pipeline.

### 10.1. Architecture

```
dlbackend/
├── server.py              # FastAPI app, /api/dl/* endpoints, model loading
├── models.py              # Pydantic request/response schemas
├── default_classes.py     # 400 default object classes (indoor, outdoor, natural, general)
├── detectors/
│   ├── base.py            # BaseDetector ABC (detect, is_ready)
│   ├── yolo_world.py      # YOLOWorldDetector (ultralytics YOLOWorld)
│   └── grounding_dino.py  # GroundingDINODetector (HF transformers)
├── .env                   # Model configuration
├── requirements.txt       # Standalone dependencies
├── nginx.conf             # nginx reverse proxy config for RunPod deployment
├── Dockerfile             # Docker image with CUDA + nginx
├── start.sh               # RunPod startup script
└── README.md              # Usage documentation
```

### 10.2. Detection Pipeline

```
Client (RemoteYOLOv8Detector)
│
├── POST /api/dl/yoloworld
│   └── YOLOWorldDetector
│       ├── model.set_classes(classes)
│       ├── model.predict(image)
│       └── Convert xyxy → xywh (pixel coords)
│
├── POST /api/dl/grounding-dino
│   └── GroundingDINODetector
│       ├── Join classes → "person . chair . table ."
│       ├── processor(image, text) → model(**inputs)
│       ├── post_process_grounded_object_detection()
│       └── Convert boxes → xywh (pixel coords)
│
└── GET /api/dl/health
```

### 10.3. API Contract

Both endpoints accept the same request and return the same response format:

**Request:**
```json
{
  "image_b64": "<base64-encoded JPEG/PNG>",
  "classes": ["person", "chair"]
}
```

`classes` is optional — if omitted, ~400 default classes (indoor + outdoor + natural + general objects) are used.

**Response:**
```json
[
  { "class_name": "person", "xywh": [320.5, 240.0, 80.0, 160.0], "confidence": 0.92 }
]
```

- `xywh`: bounding box as `[center_x, center_y, width, height]` in pixel coordinates
- `confidence`: detection confidence score

### 10.4. Configuration

Models are configured via `dlbackend/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `YOLO_WORLD_MODEL` | `yolov8x-worldv2.pt` | YOLO-World model variant |
| `GROUNDING_DINO_MODEL` | `IDEA-Research/grounding-dino-tiny` | Grounding DINO HuggingFace model ID |

### 10.5. Deployment

The DL backend is designed to run on a GPU server (e.g. RunPod) separately from the main GO2 server. See `dlbackend/README.md` for deployment instructions.

Integration with the main server requires only updating `DEFAULT_REMOTE_DETECTOR_URL` in the main `.env`:

```env
DEFAULT_REMOTE_DETECTOR_URL=https://<host>/api/dl/yoloworld
# or
DEFAULT_REMOTE_DETECTOR_URL=https://<host>/api/dl/grounding-dino
```