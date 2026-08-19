# Development Guide

This document provides context for developers working on the GO2 Middle Layer. It covers device bypass, graceful shutdown, port handling, and architectural patterns.

---

## 1. Running Without Full GO2 Hardware (Bypass Mode)

The server is designed to **run on any machine** — even without the GO2 robot, RealSense camera, ROS2, or other hardware. When optional dependencies or devices are unavailable, the server uses **stub implementations** and continues running. Affected MCP endpoints return "not available" responses instead of crashing.

### 1.1 Optional Dependencies & Stubs

| Service | Required Dependency | When Unavailable | Stub Location |
|---------|---------------------|------------------|---------------|
| Depth camera | `pyrealsense2` | Not installed | `impl/depth_camera_service_stub.py` |
| ROS2 state | `rclpy` | Not installed | `impl/ros2_state_service_stub.py` |
| RPC camera | `unitree_sdk2py` | Not installed | `impl/rpc_camera_service_stub.py` |
| Sport control | `unitree_sdk2py` | Not installed | `impl/sdk_sport_service_stub.py` |
| Echo state | `ros2` CLI | Not in PATH | Logs warning, returns `None` |
| Local camera | OpenCV + USB cam | Device not found | Logs warning, returns `None` |
| Audio capture | `sounddevice` + `vosk` | Device error | Logs error, returns `[]` |

### 1.2 How Bypass Works

In `dependencies/__init__.py`, services are imported with `try/except`:

```python
try:
    from impl.depth_camera_service import DepthCameraService
except ImportError:
    from impl.depth_camera_service_stub import DepthCameraServiceStub as DepthCameraService
```

- **Import-time failure** (e.g. `pyrealsense2` not installed) → stub is used.
- **Runtime failure** (e.g. camera device not found) → real service handles it gracefully (log + return `None`).

### 1.3 Minimal Setup for Development

You can run the server with only:

```bash
conda create -n go2 python=3.12 -y && conda activate go2
make install                    # Install dependencies + pytest
make run                        # Run server (from project root)
```

Or manually:

```bash
cd src && pip install -r requirements.txt
pip install pytest pytest-asyncio
python src/server.py
```

The server will start. Endpoints like `/sport/mcp`, `/camera/mcp`, `/depth_camera/mcp`, `/sport_state/mcp` will return "not available" until you install the corresponding SDK/hardware.

### 1.4 Enabling Full Functionality

| Feature | Install / Connect |
|---------|-------------------|
| Robot control & RPC camera | `unitree_sdk2_python` + network to robot |
| Depth camera | `conda install -c conda-forge pyrealsense2` + RealSense |
| Object detection (depth cam) | Run `dlbackend/` on a GPU server, set `DEFAULT_REMOTE_DETECTOR_URL` |
| Robot state | ROS2 + `rclpy` or `ros2 topic echo` |
| Local camera | USB camera (device ID in `LOCAL_CAMERA_DEVICE_ID`) |
| Voice commands | `sounddevice`, `vosk` + microphone |

---

## 2. Port Handling

### 2.1 Port Fallback

By default, if the requested port (e.g. 8001) is already in use, the server **tries the next available port** (8002, 8003, … up to 10 attempts).

```bash
python src/server.py                    # Uses 8001, or 8002 if 8001 is busy
python src/server.py --port 9000        # Uses 9000, or 9001, 9002, …
python src/server.py --no-port-fallback # Fails if port is in use (no fallback)
```

### 2.2 Environment Variables

- `PORT` — default port (default: 8001)
- `UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN` — seconds to wait for graceful shutdown (default: 10)

---

## 3. Graceful Shutdown

When the server receives SIGTERM or SIGINT (e.g. Ctrl+C), it:

1. Stops accepting new connections
2. Waits for in-flight requests (up to `timeout_graceful_shutdown` seconds)
3. Cleans up services in **reverse startup order** (LIFO):
   - audio_capture → local_camera → depth_camera → rpc_camera → state_background_reader
4. Exits

### 3.1 Shutdown Order

Services are stopped in reverse order of startup so that dependent resources are released first.

### 3.2 Error Handling During Shutdown

Each service stop is wrapped in `_stop_service()`, which catches exceptions and logs them without blocking other cleanup. One failing service does not prevent others from stopping.

### 3.3 Configuration

```bash
python src/server.py --timeout-graceful-shutdown 15
# or
UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN=20 python src/server.py
```

---

## 4. Architecture Summary

### 4.1 Four-Layer Flow

```
MCP (mcps/*) → Use Cases (usecases/*) → Interfaces (interfaces/*) ← Implementations (impl/*)
```

- **MCP**: Tool definitions, delegate to controllers
- **Use cases**: Business logic, orchestration
- **Interfaces**: ABCs (contracts)
- **Implementations**: Concrete services (SDK, hardware)

### 4.2 Stub Implementations

Stubs live in `impl/*_stub.py` and implement the same interface as the real service. They:

- `start()` / `stop()` — no-op
- `get_latest_frame()` / `get_latest_state()` — return `None`
- Log a warning at init so developers know the feature is disabled

### 4.3 Adding a New Optional Service

1. Create `impl/xxx_service.py` (real implementation)
2. Create `impl/xxx_service_stub.py` (stub)
3. In `dependencies/__init__.py`:
   ```python
   try:
       from impl.xxx_service import XxxService
   except ImportError:
       from impl.xxx_service_stub import XxxServiceStub as XxxService
   ```
4. Register in `Go2MiddleLayerContainer`
5. Add start/stop to `server.py` lifespan

---

## 5. File Reference

| Path | Purpose |
|------|---------|
| `Makefile` | Server, tests, lint, format, install targets |
| `src/server.py` | FastAPI app, lifespan, port fallback, graceful shutdown |
| `src/dependencies/__init__.py` | DI container, service registration, bypass imports |
| `src/impl/*_stub.py` | Stub implementations for optional services |
| `src/interfaces/*.py` | Abstract base classes |
| `tests/` | Integration tests (pytest; require running server) |
| `docs/architecture.md` | Detailed architecture |
| `docs/features.md` | API reference |
| `docs/DEVELOPMENT.md` | This file — bypass mode, port, shutdown, Makefile |
| `CLAUDE.md` | Quick reference for AI assistants |
| `dlbackend/` | DL Backend — YOLO-World & Grounding DINO detection server |
| `dlbackend/README.md` | DL Backend setup, deployment, API docs |

---

## 6. Makefile

The project provides a Makefile for common tasks. Run `make help` to list all targets.

### 6.1 Server

| Target | Description |
|--------|-------------|
| `make run` | Run server in foreground (port 8001) |
| `make run-bg` | Run server in background |
| `make kill-server` | Kill process on port 8001 |

### 6.2 Tests (requires running server on port 8001, except `test-yolo`)

| Target | Description |
|--------|-------------|
| `make test` / `make test-all` | Run all pytest tests |
| `make test-sport` | Sport MCP tools |
| `make test-sport-state` | Sport state |
| `make test-rpc-cam` | RPC camera |
| `make test-depth-cam` | Depth camera |
| `make test-local-cam` | Local camera |
| `make test-speaker` | Speaker/TTS |
| `make test-audio-capture` | Audio capture |
| `make test-yolo` | YOLO detector (no server required) |

### 6.3 Code Quality

| Target | Description |
|--------|-------------|
| `make lint` | Run ruff check |
| `make format` | Run black + ruff format |

### 6.4 Setup

| Target | Description |
|--------|-------------|
| `make install` | Install dependencies + pytest |
| `make clean` | Remove `__pycache__`, `.pytest_cache` |

---

## 7. Lint

Before committing, run:

```bash
make lint
make format
```

Or manually:

```bash
black src/
ruff check src/
```

---

## 8. Common Tasks

### Kill process on port 8001

```bash
make kill-server
# or: lsof -ti :8001 | xargs kill -9
```

### Run server with verbose logging

```bash
LOG_LEVEL=DEBUG python src/server.py
```

### Test health endpoint

```bash
curl http://localhost:8001/health
```

### Run specific test suite

```bash
make test-sport        # pytest
make run-sport         # Run test script directly (no pytest)
```

### Download pre-recorded audio (Speaker)

The `recorded_audio_speak` tool requires WAV files in `SPEAKER_AUDIO_DIR`. Download them with:

```bash
pip install py7zr  # required for dog.7z extraction
python scripts/download_recorded_audio.py
# or: make download-audio
```

Uses OpenGameArt dog.7z pack (barks, growls, whimpers). Use `--fallback` if py7zr unavailable.
