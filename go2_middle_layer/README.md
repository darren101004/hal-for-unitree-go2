# GO2 Middle Layer

A middle-layer server for the Unitree GO2 robot, providing MCP (Model Context Protocol) endpoints to:

- Control sport mode (move, stand, lie down, etc.)
- Read robot state (sport state, IMU, etc.)
- Capture images from the RPC camera (the built-in camera on the robot), local camera (an additional wide-angle camera), and depth camera (Intel RealSense)
- Analyze images with YOLO object detection and captioning

## Prerequisites

- Python 3.12
- `unitree_sdk2_python` (for robot control)
- Network connection to the GO2 robot
- Intel RealSense camera (optional, for depth imaging)

## Installation

### 1. Create a conda environment

```bash
conda create -n go2 python=3.12 -y
conda activate go2
```

### 2. Install dependencies

```bash
cd go2_middle_layer/src
pip install -r requirements.txt
```

### 3. Install `unitree_sdk2_python`

Follow the instructions at: https://github.com/unitreerobotics/unitree_sdk2_python

### 4. Install `pyrealsense2` (optional)

The depth camera (Intel RealSense) is **optional**. The server runs without it; the `/depth_camera` MCP will return "No frame available" until you install `pyrealsense2` and connect a RealSense device.

**To enable depth camera:**

**Option 1 — conda-forge (recommended):**

```bash
conda install -c conda-forge pyrealsense2
```

**Option 2 — From the official documentation:**

See instructions at: https://github.com/realsenseai/librealsense/blob/master/wrappers/python/readme.md


```bash
git clone https://github.com/realsenseai/librealsense.git
cd librealsense


mkdir build
cd build

cmake .. \
-DBUILD_PYTHON_BINDINGS=true \
-DPYTHON_EXECUTABLE=$(which python)

make -j$(nproc)
sudo make install
```

## Configuration

The server reads configuration from environment variables or a `.env` file placed in `src/`. Supported variables:

| Variable                      | Default                                 | Description                                         |
|-------------------------------|-----------------------------------------|-----------------------------------------------------|
| `PORT`                        | `8001`                                  | Server port                                         |
| `ENV`                         | `local`                                 | Environment (`local` / `production`)                |
| `LOG_LEVEL`                   | `INFO`                                  | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)     |
| `LOG_TO_FILE`                 | `true`                                  | Write logs to file                                  |
| `LOGS_DIR`                    | `./logs`                                | Log file directory                                  |
| `STATE_SERVICE_MODE`          | `echo`                                  | Sport state reading mode (`echo` / `ros2`)          |
| `STATE_TOPIC`                 | `/lf/sportmodestate`                    | ROS2 topic for sport state                          |
| `STATE_NETWORK_INTERFACE`     | `eth0`                                  | Network interface connected to the robot            |
| `CAMERA_FPS`                  | `30`                                    | FPS for RPC camera                                  |
| `DEPTH_CAMERA_FPS`            | `30`                                    | FPS for depth camera                                |
| `LOCAL_CAMERA_DEVICE_ID`      | `0`                                     | Device ID for the local camera                      |
| `DEFAULT_REMOTE_DETECTOR_URL` | `http://192.168.2.179:8000/yoloworld`   | URL of the YOLO detection server                    |

## Running

From the project root, run:

```bash
cd go2_middle_layer
python src/server.py
```

The server will start at `http://0.0.0.0:8001`. If port 8001 is in use, it will try 8002, 8003, etc. up to 10 ports.

```bash
python src/server.py --port 9000
python src/server.py --no-port-fallback   # Fail if port is in use
```

### Graceful Shutdown

On SIGTERM/SIGINT (Ctrl+C), the server stops services cleanly. Configure timeout:

```bash
python src/server.py --timeout-graceful-shutdown 15
# or: UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN=20
```

## Makefile

Run `make help` to list all targets.

| Target | Description |
|--------|-------------|
| `make run` | Run server (foreground, port 8001) |
| `make run-bg` | Run server in background |
| `make kill-server` | Kill process on port 8001 |
| `make test` / `make test-all` | Run all tests (server must be running) |
| `make test-sport` | Sport MCP tools |
| `make test-sport-state` | Sport state |
| `make test-rpc-cam` | RPC camera |
| `make test-depth-cam` | Depth camera |
| `make test-local-cam` | Local camera |
| `make test-speaker` | Speaker/TTS |
| `make test-audio-capture` | Audio capture |
| `make test-yolo` | YOLO detector (no server required) |
| `make lint` | Run ruff check |
| `make format` | Run black + ruff format |
| `make install` | Install dependencies + pytest |
| `make clean` | Remove `__pycache__`, `.pytest_cache` |

## Lint

```bash
black src/
ruff check src/
```

## Development

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for:

- **Bypass mode** — run without GO2 robot, RealSense, ROS2, etc.
- **Port fallback** — automatic port selection when default is busy
- **Graceful shutdown** — clean service cleanup on SIGTERM/SIGINT
- **Makefile** — server, tests, lint, format targets
- **Architecture** — layers, stubs, adding new services

Tiếng Việt: [docs/vi/DEVELOPMENT_vi.md](docs/vi/DEVELOPMENT_vi.md)