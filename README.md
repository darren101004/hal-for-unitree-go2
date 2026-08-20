# GO2 Sport Control

FastAPI + MCP server for controlling motion (sport) and reading state on the Unitree GO2W robot.

Split out of `go2_middle_layer/`, keeping only those two paths. **`go2_middle_layer/` is now a reference-only directory** — nothing under `src/` imports from it.

## Architecture

The layering of the original repo is preserved:

```
src/
├── server.py              FastAPI app, lifespan, MCP mounts, /health + /status
├── service_registry.py    service-status registry, the source behind /status
├── paths.py               resolves paths relative to src/ (independent of cwd)
│
├── mcps/                  Transport layer — MCP tool definitions
│   ├── configs.py           logging configuration
│   ├── sport.py             stand_up, move_forward, turn_left, ...
│   └── sportstate.py        get_sport_mode_state
│
├── usecases/              Business layer — orchestration, knows nothing of the SDK
│   ├── sport_controller.py  move loop, ensure_standing, cancelling an in-flight command
│   └── state_controller.py  reads the latest state
│
├── interfaces/            Abstract contracts (ABC)
│   ├── sport.py             SportService.handle()
│   └── state.py             StateService.start/stop/get_latest_state()
│
├── impl/                  Implementation layer — the only place that touches the SDK
│   ├── sdk_sport/           control via unitree_sdk2py
│   │   ├── sdk_sport_service.py
│   │   └── sdk_sport_service_stub.py     used when unitree_sdk2py is missing
│   ├── state/               reads state over DDS, no ROS2 involved
│   │   ├── sdk_state_service.py          subscribes to sportmodestate + lowstate
│   │   └── sdk_state_service_stub.py     used when unitree_sdk2py is missing
│   └── device_watcher/      restarts services when the robot boots after the server
│
├── models/                Data types
│   ├── response.py          shared Response
│   ├── sport_option.py      command enum + API ID table + error codes
│   ├── sport_request.py     SportRequest
│   └── state.py             RobotState, SportModeEnum, GaitTypeEnum
│
└── dependencies/          DI container (dependency-injector) + settings
```

Dependencies point one way: `mcps → usecases → interfaces ← impl`. `usecases` knows only `interfaces`, never `impl` — `dependencies/` is the single place that wires the two together.

### Stub mechanism

`dependencies/_lazy_class()` imports modules lazily with a fallback. When a library is missing it switches to the stub instead of crashing:

| Missing | Falls back to | Effect |
|---|---|---|
| `unitree_sdk2py` | `SdkSportServiceStub` | every sport command returns 503 |
| `unitree_sdk2py` | `SdkSportStateServiceStub` | `get_latest_state()` returns None |

The server still boots, and `/status` reports exactly which service is broken and why. When the robot is off (the `end0` link is down) DDS cannot bind — `/status` says so plainly instead of raising a traceback.

## Requirements

Three pieces, installed in this order:

**1. The CycloneDDS C library** — no aarch64 wheel exists, so it must be built from source:

```bash
git clone -b releases/0.10.x https://github.com/eclipse-cyclonedds/cyclonedds
cd cyclonedds && mkdir -p build install && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=../install -DCMAKE_BUILD_TYPE=Release
cmake --build . --target install -j$(nproc)
export CYCLONEDDS_HOME=$(cd ../install && pwd)
```

**2. unitree_sdk2_python** — needs `CYCLONEDDS_HOME` from the step above:

```bash
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
pip install -e ./unitree_sdk2_python
```

**3. The remaining Python packages:**

```bash
pip install -r src/requirements.txt
```

**ROS2 is not required.** Both control and state reading go straight over CycloneDDS through `unitree_sdk2py`. State used to rely on `rclpy`, which is not on PyPI — it ships only with an apt-installed ROS2 distribution, so on this Debian 12 board it always fell back to the stub. It has been replaced by the SDK's `ChannelSubscriber`: same DDS bus, same packets on the wire, only the decoding Python class differs.

Topics are declared in `.env` in ROS2 form (`/lf/sportmodestate`); the service maps them to DDS form (`rt/lf/sportmodestate`) itself — that prefix is what ROS2 adds implicitly.

## Configuration

```bash
cp .env.example .env
```

The most important variable is `STATE_NETWORK_INTERFACE` — the name of the Ethernet port facing the robot, used by **both** the sport service and the state service:

```
STATE_NETWORK_INTERFACE=end0
```

On the OrangePi board that port is named `end0` (Allwinner `dwmac-sunxi` driver), **not** `eth0` or `enp2s0` as the Unitree documentation assumes.

## Running

```bash
make run                  # or: python src/server.py
```

The server comes up on `http://0.0.0.0:8001`. If that port is busy it tries 8002, 8003, ... up to 10 ports.

| Endpoint | Purpose |
|---|---|
| `GET /health` | alive or not |
| `GET /status` | which services are available, and any errors |
| `/sport/mcp` | MCP for motion control |
| `/sport_state/mcp` | MCP for state reading |

## Tests

Require a running server:

```bash
make test-sport           # sport MCP tools
make test-sport-state     # state reading
```

> **Warning:** `test_sport_mcp_tools.py` issues commands that make the **robot physically move**. Check the space around it before running.

## Differences from `go2_middle_layer/`

| | Change |
|---|---|
| Layers dropped | camera (rpc/depth/local), speaker/TTS, audio capture, YOLO |
| `sport_controller` | `depth_camera_service` dependency removed; the obstacle-avoidance branch remains but is never activated |
| `impl/state/` | dropped `echo_state_service` (deprecated, required the `ros2 topic echo` CLI) and both `rclpy`-based implementations; replaced by `sdk_state_service` using DDS directly |
| ROS2 dependency | fully removed — no `rclpy`, no `unitree_go.msg`, no `ros2` CLI anywhere |
| Default interface | `eth0` → `end0` |
| DI provider | `state_service_using_ros2` → `state_service` |
| `service_registry` | down to 3 entries: `sport`, `state`, `device_watcher` |
| MCP tool | `get_sport_mode_state_using_ros2` kept as a deprecated alias pointing at the same place as `get_sport_mode_state` |
| Config dropped | `STATE_SERVICE_MODE` (declared but never read) |
| `requirements.txt` | 30 packages → 10 packages |
