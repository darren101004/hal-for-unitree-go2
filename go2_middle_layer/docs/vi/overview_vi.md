# GO2 Middle Layer - Tổng quan dự án

## Mục đích

Repo này là **tầng trung gian (middle layer)** để điều khiển **robot chó 4 chân Unitree GO2** thông qua giao thức **MCP (Model Context Protocol)**.

Nói đơn giản: nó cho phép **AI Agent** (hoặc bất kỳ client HTTP nào) ra lệnh cho con robot đi, đứng, quay, quan sát môi trường qua camera, nhận diện vật thể, và mô tả cảnh vật — tất cả thông qua API.

---

## Kiến trúc tổng quan

```
┌──────────────────────────────────────────────────────┐
│  AI Agent / Client                                   │
└──────────────────┬───────────────────────────────────┘
                   │ HTTP (MCP protocol)
┌──────────────────▼───────────────────────────────────┐
│  FastAPI Server (server.py, port 8001)               │
│  Routes: /sport, /sport_state, /camera,              │
│          /depth_camera, /local_camera, /speaker,     │
│          /health                                     │
└──────────────────┬───────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────┐
│  MCP Tools Layer (mcps/*.py)                         │
│  Khai báo các tool MCP, chuyển request xuống layer   │
│  dưới và đóng gói response trả về.                   │
└──────────────────┬───────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────┐
│  Use Cases / Controllers (usecases/*.py)             │
│  Business logic: đảm bảo robot đứng trước khi đi,   │
│  kiểm tra chướng ngại vật, tính duration di chuyển,  │
│  encode ảnh base64...                                │
└──────────────────┬───────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────┐
│  Interfaces (interfaces/*.py)                        │
│  Abstract Base Classes: StateService, SportService,  │
│  CameraService                                       │
└──────────────────┬───────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────┐
│  Implementations (impl/*.py)                         │
│  Giao tiếp trực tiếp với phần cứng: Unitree SDK,    │
│  ROS2, RealSense, OpenCV                             │
└──────────────────────────────────────────────────────┘
```

---

## Cấu trúc thư mục

```
go2_middle_layer/
├── README.md
├── LICENSE                          # Apache 2.0
├── overview_vi.md                   # File này
├── .gitignore
│
├── src/
│   ├── server.py                    # Entry point: FastAPI app, mount MCP apps, lifecycle
│   ├── requirements.txt             # Python dependencies
│   │
│   ├── dependencies/
│   │   └── __init__.py              # DI container (Go2MiddleLayerContainer), settings
│   │
│   ├── models/
│   │   ├── state.py                 # RobotState, SportModeStateDict, SportModeEnum, GaitTypeEnum
│   │   ├── sport_request.py         # SportRequest, SportResponse, SportHandler
│   │   ├── sport_option.py          # SportOption enum, API_ID_MAP, RESPONSE_CODE_MAP
│   │   └── response.py             # Response model chung (success, message, data, code)
│   │
│   ├── interfaces/                  # Abstract Base Classes
│   │   ├── state.py                 # StateService: start(), stop(), get_latest_state()
│   │   ├── sport.py                 # SportService: handle(SportRequest) -> Response
│   │   ├── camera.py               # CameraService: start(), stop(), get_latest_frame()
│   │   └── speaker.py             # SpeakerService: speak(), aspeak(), play_file(), aplay_file()
│   │
│   ├── impl/                        # Concrete implementations
│   │   ├── sdk_sport_service.py     # SdkSportService — gửi lệnh qua Unitree SDK
│   │   ├── echo_state_service.py    # Ros2EchoSportStateService — đọc state bằng `ros2 topic echo`
│   │   ├── ros2_state_service.py    # Ros2SportStateService — đọc state bằng rclpy (separate process)
│   │   ├── sdk_state_service.py     # SDKSubscriberSportStateService — đọc state bằng rclpy (same process)
│   │   ├── rpc_camera_service.py    # RpcCameraService — camera trên robot qua Unitree VideoClient
│   │   ├── depth_camera_service.py  # DepthCameraService — Intel RealSense depth camera
│   │   ├── local_camera_service.py  # LocalCameraService — USB camera qua OpenCV
│   │   ├── utils.py                 # build_depth_frame_info, estimate_position, mô tả ngôn ngữ tự nhiên
│   │   └── speaker/                 # Triển khai Speaker/TTS
│   │       ├── __init__.py
│   │       ├── base.py              # SpeakerDeviceBase, SyncSpeakerDeviceBase, AsyncSpeakerDeviceBase
│   │       ├── models.py            # Enum RecordedAudio, SpeakerDeviceInfo
│   │       ├── tts.py               # TTS engines: openai_tts_realtime, piper_tts_realtime
│   │       ├── openai_speaker_service.py  # SpeakerService → OpenAI TTS API
│   │       └── piper_speaker_service.py   # SpeakerService → Piper TTS (offline)
│   │
│   ├── mcps/                        # MCP tool definitions (transport layer)
│   │   ├── configs.py               # Settings (env, log), setup_logging()
│   │   ├── sport.py                 # Sport MCP tools
│   │   ├── sportstate.py            # State MCP tools
│   │   ├── rpc_camera.py            # RPC camera MCP tools
│   │   ├── depth_camera.py          # Depth camera MCP tools
│   │   ├── local_camera.py          # Local camera MCP tools
│   │   └── speaker.py              # Speaker/TTS MCP tools
│   │
│   ├── usecases/                    # Business logic / Controllers
│   │   ├── sport_controller.py      # SportController — điều khiển vận động
│   │   ├── state_controller.py      # StateController — đọc trạng thái robot
│   │   ├── rpc_camera_controller.py # RpcCameraController — chụp ảnh từ robot camera
│   │   ├── depth_camera_controller.py # DepthCameraController — chụp + phân tích depth
│   │   ├── local_camera_controller.py # LocalCameraController — chụp ảnh từ USB camera
│   │   └── speaker_controller.py   # SpeakerController — điều phối TTS và phát audio
│   │
│   └── utils/
│       ├── captioning.py            # Captioner ABC, RemoteCaptioner (gọi API mô tả ảnh)
│       └── yolov8/
│           ├── base.py              # ObjectDetector ABC, DEFAULT_CLASSES
│           ├── yolov8_detector.py   # YOLOv8Detector — chạy YOLO local
│           └── yolov8_remote_detector.py # RemoteYOLOv8Detector — gọi YOLO qua HTTP
│
└── tests/                           # Integration tests (gọi HTTP tới server đang chạy)
    ├── test_sport_mcp_tools.py
    ├── test_sport_state.py
    ├── test_rpc_cam_mcp_tools.py
    ├── test_local_cam_mcp_tools.py
    ├── test_depth_cam_mcp_tools.py
    ├── test_speaker_mcp_tools.py
    └── test_yolo.py
```

---

## 6 nhóm chức năng chính

### 1. Sport Control — Điều khiển vận động

Cho phép AI Agent ra lệnh cho robot di chuyển.

| MCP Tool | Mô tả | Tham số |
|----------|--------|---------|
| `stop_move` | Dừng di chuyển | — |
| `stand_up` | Đứng lên | — |
| `stand_down` | Ngồi xuống | — |
| `move_forward` | Đi tới | `distance` (cm, max 300) |
| `move_backward` | Đi lùi | `distance` (cm, max 300) |
| `turn_left` | Quay trái tại chỗ | `angle` (độ, 0–180) |
| `turn_right` | Quay phải tại chỗ | `angle` (độ, 0–180) |
| `step_to_left` | Bước ngang trái | `distance` (cm, max 300) |
| `step_to_right` | Bước ngang phải | `distance` (cm, max 300) |
| `move_to_target_position` | Quay + đi tới mục tiêu | `angle` (-180..180), `distance` (cm) |

**Luồng xử lý bên trong:**
1. `SportController` nhận lệnh, **tự động đứng dậy** nếu robot chưa đứng.
2. Tính thời gian di chuyển dựa trên `distance / speed`.
3. Gửi lệnh `Move(vx, vy, vyaw)` liên tục trong vòng lặp cho đến khi hết thời gian.
4. Khi `move_forward` hoặc `move_to_target_position`, **kiểm tra chướng ngại vật** qua depth camera (dừng nếu vật thể < 400mm).
5. Lệnh mới sẽ **cancel lệnh đang chạy** thông qua `asyncio.Event`.

**Thông số mặc định (SportPolicy):**
- Tốc độ di chuyển: 0.4 m/s
- Tốc độ xoay: 0.5 rad/s
- Loop interval: 10ms

### 2. Sport State — Đọc trạng thái robot

Lấy dữ liệu realtime từ robot: vị trí, vận tốc, IMU, chế độ hoạt động...

| MCP Tool | Mô tả |
|----------|--------|
| `get_sport_mode_state_using_echo` | Đọc state bằng `ros2 topic echo` (subprocess) |
| `get_sport_mode_state_using_ros2` | Đọc state bằng rclpy subscriber (separate process) |
| `get_sport_mode_state` | Alias → dùng phương thức echo |

**Dữ liệu trạng thái trả về (`RobotState`):**

| Field | Kiểu | Ý nghĩa |
|-------|------|---------|
| `stamp` | `{sec, nanosec}` | Timestamp |
| `error_code` | `uint32` | Mã lỗi |
| `imu_state` | `{quaternion, gyroscope, accelerometer, rpy, temperature}` | Dữ liệu IMU |
| `mode` | `uint8` | Chế độ: 0=Idle, 1=Standing, 2=Walking_vel, 5=Stand_down, 6=Stand_up, 7=Damping... |
| `gait_type` | `uint8` | Kiểu dáng đi: 0=Idle, 1=Trot walking, 2=Trot running, 3=Stairs... |
| `position` | `float[3]` | Vị trí (x, y, z) |
| `velocity` | `float[3]` | Vận tốc (vx, vy, vz) |
| `yaw_speed` | `float` | Tốc độ xoay |
| `foot_raise_height` | `float` | Chiều cao nâng chân |
| `body_height` | `float` | Chiều cao thân |
| `range_obstacle` | `float[4]` | Khoảng cách chướng ngại vật 4 hướng |
| `foot_force` | `int[4]` | Lực tác dụng lên 4 chân |
| `foot_position_body` | `float[12]` | Vị trí 4 chân trong hệ tọa độ thân (3 tọa độ × 4 chân) |
| `foot_speed_body` | `float[12]` | Tốc độ 4 chân |

**Có 3 implementation đọc state:**

| Class | Cơ chế | Ưu điểm | Nhược điểm |
|-------|--------|---------|------------|
| `Ros2EchoSportStateService` | Subprocess `ros2 topic echo` + parse YAML | Đơn giản, không cần rclpy trong process chính | Parse YAML chậm hơn |
| `Ros2SportStateService` | rclpy subscriber trong **separate process**, gửi state qua `mp.Queue` | Isolation tốt, không ảnh hưởng main process | Overhead IPC qua Queue |
| `SDKSubscriberSportStateService` | rclpy subscriber trong **same process** (background thread) | Nhanh nhất, không overhead IPC | Cần rclpy init trong main process |

Server khởi động **cả echo và ros2** cùng lúc (xem `StateController.start_state_service()`).

### 3. RPC Camera — Camera trên robot

Chụp ảnh từ camera gắn sẵn trên robot GO2.

| MCP Tool | Mô tả |
|----------|--------|
| `capture_image` | Lấy frame mới nhất, trả về ảnh base64 |

**Cách hoạt động:**
- Background thread liên tục gọi `VideoClient.GetImageSample()` từ Unitree SDK.
- Lưu frame mới nhất vào buffer (`_latest_frame`).
- Khi client gọi `capture_image`, trả ngay frame trong buffer → không có latency chờ capture.

### 4. Depth Camera — Camera chiều sâu (Intel RealSense)

Chụp ảnh RGB + depth, detect vật thể, ước lượng vị trí 3D.

| MCP Tool | Mô tả |
|----------|--------|
| `capture_image` | Lấy frame + phân tích → trả về ảnh base64, danh sách vật thể, mô tả ngôn ngữ tự nhiên |

**Pipeline xử lý khi gọi `capture_image`:**

```
RealSense frame (RGB + Depth)
       │
       ├──→ Align depth với color
       ├──→ YOLO detect vật thể (remote HTTP server)
       └──→ Captioning mô tả cảnh (remote HTTP server, hiện đang tắt)
              │
              ▼
     Với mỗi vật thể detected:
       1. Lấy bounding box → tính center pixel (u, v)
       2. Lấy depth tại ROI → filter bằng box filter → lấy min depth
       3. Nếu depth > 6000mm → xếp vào "far objects" (bỏ qua)
       4. estimate_position(depth, pixel, intrinsics) → tọa độ 3D (x, y, z) mm
       5. get_angle_and_distance(x, y, z) → khoảng cách (cm) + góc (độ)
              │
              ▼
     Tạo mô tả ngôn ngữ tự nhiên, ví dụ:
       "At 2026-03-03 14:30:00:
        1. person_1 at 120 centimeters, 25 degrees to the left of the center.
        2. chair_1 at 200 centimeters, directly in front of the center."
              │
              ▼
     Response: {
       "data": base64_image,
       "extra_data": {
         "objects": [...],
         "natural_language_description": "..."
       }
     }
```

**Hàm `estimate_position`** chuyển từ pixel + depth sang tọa độ 3D:
- Dùng camera intrinsics (fx, fy, ppx, ppy) để project ngược từ 2D → 3D.
- Bù offset 35mm trên trục X (khoảng cách giữa camera depth và camera color).

### 5. Local Camera — Camera USB gắn ngoài

Chụp ảnh từ webcam / USB camera thông thường.

| MCP Tool | Mô tả |
|----------|--------|
| `capture_image` | Lấy frame mới nhất, trả về ảnh PNG base64 |

Hoạt động giống RPC Camera: background thread capture liên tục qua OpenCV `VideoCapture`, lưu buffer, trả frame khi client request.

### 6. Speaker — Phát giọng nói & âm thanh

Cho phép robot nói text qua TTS và phát các clip âm thanh ghi sẵn.

| MCP Tool | Mô tả | Tham số |
|----------|--------|---------|
| `speak_text` | Nói text ra loa bằng TTS | `text` (str), `interrupt` (bool, mặc định false) |
| `recorded_audio_speak` | Phát clip âm thanh ghi sẵn | `audio_name` (enum: bark, happy, sad, alert, greeting, goodbye, acknowledge, error, confused), `interrupt` (bool) |
| `stop_speaking` | Dừng mọi âm thanh đang phát | — |

**Hai implementation TTS:**

| Class | Engine | Ưu điểm | Nhược điểm |
|-------|--------|---------|------------|
| `OpenAISpeakerService` | OpenAI TTS API (streaming) | Chất lượng cao, nhiều giọng | Cần kết nối internet, tốn API key |
| `PiperSpeakerService` | Piper (model ONNX local) | Offline, độ trễ thấp | Chất lượng thấp hơn OpenAI |

Chọn engine qua biến `SPEAKER_TTS_ENGINE` (`openai` hoặc `piper`). Sử dụng `Selector` provider của dependency-injector.

**Luồng xử lý `speak_text`:**
1. `SpeakerController` nhận text, chuyển tới `SpeakerService.aspeak()`.
2. TTS engine sinh audio chunks (24kHz mono).
3. Resampler chuyển đổi sang 48kHz.
4. `_adapt_channels` khớp số kênh với output stream.
5. `sounddevice.OutputStream` phát âm thanh.

**Luồng xử lý `recorded_audio_speak`:**
1. Tra cứu file: `{SPEAKER_AUDIO_DIR}/{audio_name}.wav`.
2. `soundfile` đọc WAV theo chunks → resample → phát qua `sounddevice`.

---

## Dependency Injection

Project sử dụng `dependency-injector` để quản lý các service singleton.

**Container (`Go2MiddleLayerContainer`):**

| Provider | Class | Ghi chú |
|----------|-------|---------|
| `sport_service` | `SdkSportService` | Gửi lệnh vận động qua Unitree SDK |
| `state_service_using_echo` | `Ros2EchoSportStateService` | Đọc state bằng subprocess |
| `state_service_using_ros2` | `Ros2SportStateService` | Đọc state bằng rclpy (separate process) |
| `rpc_camera_service` | `RpcCameraService` | Camera robot |
| `depth_camera_service` | `DepthCameraService` | Camera RealSense |
| `local_camera_service` | `LocalCameraService` | Camera USB |
| `speaker_service_openai` | `OpenAISpeakerService` | TTS qua OpenAI API |
| `speaker_service_piper` | `PiperSpeakerService` | TTS offline qua Piper |
| `speaker_service` | Selector (openai/piper) | Service speaker đang hoạt động |

Các controller dùng decorator `@inject` + `Provide[...]` để nhận service từ container.

---

## Lifecycle (Khởi động / Tắt)

Khi server FastAPI khởi động (`combined_lifespan` trong `server.py`):

**Startup:**
1. Wire DI container
2. Start state background reader (cả echo và ros2)
3. Start RPC camera background capture (30 FPS)
4. Start depth camera background capture (30 FPS)
5. Start local camera background capture (30 FPS)
6. Enter lifespan cho tất cả MCP apps

**Shutdown:**
1. Stop RPC camera
2. Stop depth camera
3. Stop local camera
4. Stop state reader

---

## Cấu hình

Đọc từ file `.env` hoặc environment variables:

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `STATE_SERVICE_MODE` | `echo` | Chế độ đọc state |
| `STATE_TOPIC` | `/lf/sportmodestate` | ROS2 topic |
| `STATE_NETWORK_INTERFACE` | `eth0` | Network interface cho Unitree SDK |
| `CAMERA_FPS` | `30` | FPS camera robot |
| `DEPTH_CAMERA_FPS` | `30` | FPS depth camera |
| `LOCAL_CAMERA_DEVICE_ID` | `0` | OpenCV camera device index |
| `DEFAULT_REMOTE_DETECTOR_URL` | `http://192.168.2.179:8000/yoloworld` | URL server YOLO |
| `ENV` | `local` | Môi trường |
| `LOGS_DIR` | `./logs` | Thư mục log |
| `LOG_LEVEL` | `INFO` | Mức log |
| `LOG_TO_FILE` | `True` | Ghi log ra file |
| `SPEAKER_TTS_ENGINE` | `openai` | Engine TTS: `openai` hoặc `piper` |
| `SPEAKER_DEVICE_ID` | `None` | ID thiết bị âm thanh (None = mặc định hệ thống) |
| `SPEAKER_SAMPLE_RATE` | `48000` | Sample rate đầu ra (Hz) |
| `SPEAKER_BLOCK_SIZE` | `1024` | Kích thước block âm thanh |
| `SPEAKER_CHANNELS` | `1` | Số kênh đầu ra |
| `OPENAI_API_KEY` | `""` | API key cho OpenAI TTS |
| `OPENAI_BASE_URL` | `None` | URL base tùy chỉnh cho OpenAI API |
| `TTS_MODEL` | `gpt-4o-mini-tts` | Model TTS OpenAI |
| `TTS_VOICE` | `coral` | Giọng nói OpenAI TTS |
| `DEFAULT_PIPER_MODEL` | `en_US-lessac-medium.onnx` | File model Piper ONNX |
| `SPEAKER_AUDIO_DIR` | `/opt/doggi/data/audio` | Thư mục chứa file `.wav` ghi sẵn |

---

## Công nghệ sử dụng

| Thành phần | Công nghệ |
|------------|-----------|
| Web framework | FastAPI |
| Giao thức AI Agent | FastMCP (Model Context Protocol) |
| Dependency Injection | dependency-injector |
| Validation | Pydantic, pydantic-settings |
| Robot SDK | unitree_sdk2py (SportClient, VideoClient) |
| ROS2 | rclpy, unitree_go (SportModeState message) |
| Depth camera | pyrealsense2 (Intel RealSense D435/D455) |
| Computer Vision | OpenCV, Ultralytics YOLOv8 |
| Image captioning | Remote HTTP API |
| Async HTTP | aiohttp, aiofiles |
| Audio / TTS | sounddevice, soundfile, soxr, OpenAI TTS API, Piper TTS |

---

## Phần cứng liên quan

| Thành phần | Phần cứng |
|------------|-----------|
| Robot | Unitree GO2 (robot chó 4 chân) |
| Giao tiếp sport | Unitree SDK2 qua DDS (ethernet) |
| Giao tiếp state | ROS2 topic `/lf/sportmodestate` |
| Camera robot | Camera tích hợp trên GO2, truy cập qua VideoClient |
| Depth camera | Intel RealSense (D435/D455), kết nối USB |
| Local camera | Webcam / USB camera bất kỳ |
| Speaker | Thiết bị âm thanh hệ thống (qua sounddevice/PortAudio) |
| YOLO server | Server riêng chạy YOLOWorld, mặc định `192.168.2.179:8000` |
| Captioning server | Server riêng, mặc định `14.225.217.119:8182` (hiện đang tắt trong code) |

---

## Cách chạy

```bash
# Từ thư mục gốc project
make install    # Cài dependencies + pytest
make run        # Chạy server (port 8001)
```

Hoặc thủ công:

```bash
cd src
pip install -r requirements.txt

# Chạy server
python server.py --port 8001

# Hoặc dùng uvicorn
uvicorn server:app --host 0.0.0.0 --port 8001
```

Xem [docs/vi/DEVELOPMENT_vi.md](DEVELOPMENT_vi.md) để biết thêm về Makefile, bypass mode, và các lệnh phát triển.

**Yêu cầu:**
- Python 3.10+
- ROS2 đã cài và sourced (cần cho state service)
- Unitree SDK2 Python (`unitree_sdk2py`, `unitree_go`) đã cài
- Intel RealSense SDK + `pyrealsense2` (nếu dùng depth camera)
- Kết nối ethernet tới robot GO2 qua interface được cấu hình (mặc định `eth0`)
- YOLO server đang chạy tại URL được cấu hình (nếu dùng depth camera detection)

---

## API Endpoints

| Path | Protocol | Chức năng |
|------|----------|-----------|
| `GET /health` | HTTP | Health check |
| `/sport/mcp` | MCP over HTTP | Điều khiển vận động |
| `/sport_state/mcp` | MCP over HTTP | Đọc trạng thái robot |
| `/camera/mcp` | MCP over HTTP | Camera trên robot |
| `/depth_camera/mcp` | MCP over HTTP | Depth camera RealSense |
| `/local_camera/mcp` | MCP over HTTP | Camera USB local |
| `/speaker/mcp` | MCP over HTTP | Speaker / TTS |

Tất cả MCP endpoints sử dụng **Streamable HTTP transport** (stateless).

---

## Ví dụ luồng dữ liệu

### AI Agent muốn robot đi tới 50cm

```
Agent → call_tool("move_forward", {distance: 50})
  → mcps/sport.py → sport_controller.move_forward(50)
    → Kiểm tra state → robot chưa đứng → gửi RECOVERY_STAND
    → Tính duration = 0.5m / 0.4m/s = 1.25s
    → Loop 1.25s:
        - Kiểm tra chướng ngại vật qua depth camera (< 400mm → dừng)
        - Gửi SportClient.Move(vx=0.4, vy=0, vyaw=0)
        - Sleep 10ms
    → Gửi STOP_MOVE
    → Response: "move forward completed. Successfully moved 50 centimeters"
```

### AI Agent muốn nhìn xung quanh

```
Agent → call_tool("capture_image", {})  [trên /depth_camera/mcp]
  → mcps/depth_camera.py → depth_camera_controller.capture_latest_image()
    → Lấy frame mới nhất từ buffer RealSense
    → build_depth_frame_info():
        - Align depth/color
        - YOLO detect → [person, chair, table]
        - Với mỗi object: pixel → depth → 3D position
        - Tạo mô tả: "person_1 at 120cm, 25° left; chair_1 at 200cm, in front"
    → Response: {
        data: "base64_image...",
        extra_data: {
          objects: [{name: "person_1", coordinates: [x,y,z], distance: 1200}, ...],
          natural_language_description: "At 2026-03-03 14:30:00: ..."
        }
      }
```

---

## Model chung cho Response

Mọi MCP tool đều trả về cùng một format:

```python
{
    "success": bool,       # Thành công hay thất bại
    "message": str,        # Thông báo chi tiết
    "data": Any | None,    # Dữ liệu chính (base64 image, state dict...)
    "code": int,           # Mã trạng thái (0 = success, 425 = chưa sẵn sàng, 400 = lỗi...)
    "extra_data": dict | None  # Dữ liệu bổ sung (objects, description...)
}
```

---

## Sport Options đầy đủ

Robot hỗ trợ các lệnh sport sau (qua Unitree SDK):

| Lệnh | API ID | Mô tả |
|-------|--------|--------|
| DAMP | 1001 | Tắt motor (thả lỏng) |
| BALANCE_STAND | 1002 | Đứng cân bằng |
| STOP_MOVE | 1003 | Dừng di chuyển |
| STAND_UP | 1004 | Đứng lên |
| STAND_DOWN | 1005 | Ngồi xuống |
| RECOVERY_STAND | 1006 | Đứng dậy từ trạng thái bất kỳ |
| EULER | 1007 | Điều chỉnh euler angles |
| MOVE | 1008 | Di chuyển (vx, vy, vyaw) |
| SIT | 1009 | Ngồi |
| RISE_SIT | 1010 | Đứng từ tư thế ngồi |
| HELLO | 1016 | Vẫy chào |
| STRETCH | 1017 | Vươn vai |
| DANCE1 | 1022 | Nhảy kiểu 1 |
| DANCE2 | 1023 | Nhảy kiểu 2 |
| FRONT_FLIP | 1030 | Lộn trước |
| FRONT_JUMP | 1031 | Nhảy trước |
| HEART | 1036 | Tạo hình trái tim |
| BACK_FLIP | 2043 | Lộn sau |
| HAND_STAND | 2044 | Trồng chuối |
| WALK_UPRIGHT | 2050 | Đi bằng 2 chân |
| ... | ... | Và nhiều lệnh khác |
