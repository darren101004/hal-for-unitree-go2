# Kiến trúc

## 1. Cấu trúc thư mục

```
src/
├── server.py                          # FastAPI app, mount các MCP sub-app, quản lý lifecycle
├── requirements.txt                   # Các dependency Python
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
│   ├── echo_state_service.py          # StateService → subprocess ros2 topic echo
│   ├── ros2_state_service.py          # StateService → rclpy subscriber (process riêng)
│   ├── sdk_state_service.py           # StateService → rclpy subscriber (thread cùng process)
│   ├── rpc_camera_service.py          # CameraService → Unitree SDK2 VideoClient
│   ├── depth_camera_service.py        # CameraService → Intel RealSense pyrealsense2
│   ├── local_camera_service.py        # CameraService → OpenCV VideoCapture
│   ├── utils.py                       # Ước lượng vị trí 3D, xử lý depth, mô tả ngôn ngữ tự nhiên
│   ├── audio_capture/                 # Triển khai Audio Capture
│   │   ├── __init__.py
│   │   ├── audio_capture_device.py    # Thiết bị micro, hotword detection, Vosk ASR
│   │   ├── service.py                 # AudioCaptureServiceImpl (background thread)
│   │   └── service_stub.py            # AudioCaptureServiceStub (no-op khi không có mic/vosk)
│   └── speaker/                       # Triển khai Speaker/TTS
│       ├── __init__.py
│       ├── base.py                    # SpeakerDeviceBase, SyncSpeakerDeviceBase, AsyncSpeakerDeviceBase
│       ├── models.py                  # Enum RecordedAudio, SpeakerDeviceInfo, SupportedLanguages
│       ├── tts.py                     # TTS engines: openai_tts_realtime, piper_tts_realtime, Resampler
│       ├── openai_speaker_service.py  # SpeakerService → OpenAI TTS API (streaming)
│       └── piper_speaker_service.py   # SpeakerService → Piper TTS (offline, local)
│
├── mcps/
│   ├── configs.py                     # Settings, cấu hình logging
│   ├── sport.py                       # MCP tools điều khiển vận động
│   ├── sportstate.py                  # MCP tools đọc trạng thái
│   ├── rpc_camera.py                  # MCP tools camera robot
│   ├── depth_camera.py                # MCP tools depth camera
│   ├── local_camera.py               # MCP tools camera local
│   ├── speaker.py                    # MCP tools speaker/TTS
│   └── audio_capture.py              # MCP tools thu âm/ASR
│
├── usecases/
│   ├── sport_controller.py            # Điều phối di chuyển, tránh vật cản
│   ├── state_controller.py            # Định tuyến service đọc trạng thái
│   ├── rpc_camera_controller.py       # Đóng gói response camera robot
│   ├── depth_camera_controller.py     # Đóng gói response depth camera
│   ├── local_camera_controller.py     # Đóng gói response camera local
│   ├── speaker_controller.py         # Điều phối TTS, tra cứu file audio có sẵn
│   └── audio_capture_controller.py    # Lấy task âm thanh, transcribe, quản lý capture nền
│
├── models/
│   ├── response.py                    # Model Response thống nhất
│   ├── sport_request.py               # SportRequest, SportHandler
│   ├── sport_option.py                # Enum SportOption, ánh xạ API ID, mã response
│   └── state.py                       # RobotState, SportModeStateDict, IMUStateDict, các enum
│
└── utils/
    ├── captioning.py                  # Captioner ABC, RemoteCaptioner
    └── yolov8/
        ├── base.py                    # ObjectDetector ABC, danh sách class mặc định
        ├── yolov8_detector.py         # YOLOv8 detector chạy local (ultralytics)
        └── yolov8_remote_detector.py  # YOLO detector gọi qua HTTP
```

## 2. Tổng quan cấp cao

GO2 Middle Layer là một **FastAPI server** bọc các SDK cấp thấp, ROS2 và giao diện phần cứng của robot Unitree GO2 phía sau một tập các endpoint **MCP (Model Context Protocol)**. Điều này cho phép AI agent (LLM) điều khiển robot và cảm nhận môi trường thông qua các lệnh gọi tool đơn giản qua HTTP.

```
┌─────────────────────────────────────────────────────────────┐
│                      AI Agent / LLM                         │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP (MCP qua Streamable HTTP)
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
│  │              Tầng MCP (mcps/*.py)                                     │  │
│  │  Định nghĩa FastMCP tool + start/stop background                      │  │
│  └────┬─────────────┬───────────┬───────────┬────────┬────────┬────────┬──┘  │
│       │             │           │           │        │        │        │     │
│  ┌────▼─────────────▼───────────▼───────────▼────────▼────────▼────────▼──┐  │
│  │          Tầng Use Case (usecases/*.py)                                 │  │
│  │  SportController, StateController, RpcCameraController,                │  │
│  │  DepthCameraController, LocalCameraController,                         │  │
│  │  SpeakerController, AudioCaptureController                             │  │
│  └────┬─────────────┬───────────┬───────────┬────────┬────────┬────────┬──┘  │
│       │             │           │           │        │        │        │     │
│  ┌────▼─────────────▼───────────▼───────────▼────────▼────────▼────────▼──┐  │
│  │          Tầng Interface (interfaces/*.py)                              │  │
│  │  SportService (ABC), StateService (ABC), CameraService (ABC),          │  │
│  │  SpeakerService (ABC), AudioCaptureService (ABC)                       │  │
│  └────┬─────────────┬───────────┬───────────┬────────┬────────┬────────┬──┘  │
│       │             │           │           │        │        │        │     │
│  ┌────▼─────────────▼───────────▼───────────▼────────▼────────▼────────▼──┐  │
│  │       Tầng Implementation (impl/*.py)                                  │  │
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

## 3. Kiến trúc phân tầng

Codebase tuân theo **kiến trúc 4 tầng** với sự tách biệt rõ ràng:

### 3.1. Tầng 1: Tầng MCP (`mcps/*.py`)

**Vai trò:** Định nghĩa các MCP tool (bề mặt API) và quản lý lifecycle của background service.

Mỗi file khai báo một instance `FastMCP` và đăng ký tool bằng decorator `@mcp.tool()`. Tầng này rất mỏng — chỉ:
- Định nghĩa signature và mô tả của MCP tool
- Ủy thác (delegate) cho controller tương ứng ở tầng use case
- Expose các hàm `start_*` / `stop_*` được gọi bởi `server.py` trong lifespan

**Các file:**
| File | Tên FastMCP | Đường dẫn mount |
|---|---|---|
| `mcps/sport.py` | `"sport"` | `/sport/mcp` |
| `mcps/sportstate.py` | `"state"` | `/sport_state/mcp` |
| `mcps/rpc_camera.py` | `"camera"` | `/camera/mcp` |
| `mcps/depth_camera.py` | `"depth_camera"` | `/depth_camera/mcp` |
| `mcps/local_camera.py` | `"local_camera"` | `/local_camera/mcp` |
| `mcps/speaker.py` | `"speaker"` | `/speaker/mcp` |
| `mcps/audio_capture.py` | `"audio_capture"` | `/audio_capture/mcp` |

### 3.2. Tầng 2: Tầng Use Case (`usecases/*.py`) - Controllers

**Vai trò:** Điều phối business logic. Các controller phối hợp nhiều service để hoàn thành một ý định của người dùng.

Các hành vi chính được implement ở đây (không phải trong service):
- **`SportController`**: Quản lý lệnh di chuyển với async lock (chỉ một lệnh di chuyển tại một thời điểm), hủy lệnh đang chạy, tự động đứng dậy trước khi di chuyển, tránh vật cản bằng depth camera khi đi tới, và vòng lặp điều khiển vận tốc theo thời gian.
- **`StateController`**: Định tuyến request đọc trạng thái tới implementation đúng (echo hoặc ros2), quản lý lifecycle của cả hai state service.
- **`RpcCameraController` / `DepthCameraController` / `LocalCameraController`**: Chuyển đổi frame thô từ service thành object `Response` với ảnh mã hóa base64.
- **`SpeakerController`**: Ủy thác yêu cầu TTS cho `SpeakerService` đang hoạt động, tra cứu đường dẫn file audio từ enum, và xử lý ngắt speaker.
- **`AudioCaptureController`**: Lấy các task giọng nói đang chờ từ `AudioCaptureService`, transcribe audio bên ngoài, và quản lý lifecycle của capture nền. Kiểm tra tính khả dụng qua `service_registry` trước khi gọi service.

Dependency được inject vào các method của controller qua decorator `@inject` + `Provide[...]` từ `dependency-injector`.

### 3.3. Tầng 3: Tầng Interface (`interfaces/*.py`)

**Vai trò:** Định nghĩa các contract trừu tượng (ABC) mà implementation phải tuân theo. Điều này tách rời tầng use case khỏi implementation cụ thể.

```
interfaces/
├── sport.py    → SportService(ABC):  handle(SportRequest) → Response
├── state.py    → StateService(ABC):  start(), stop(), get_latest_state()
├── camera.py   → CameraService(ABC): start(fps), stop(), get_latest_frame()
├── speaker.py  → SpeakerService(ABC): speak(), aspeak(), play_file(), aplay_file(), interrupt_all_task()
└── audio.py    → AudioCaptureService(ABC): start(), stop(), get_pending_tasks(), transcribe_audio()
```

`StateService`, `CameraService`, và `AudioCaptureService` đều tuân theo **pattern background service**: `start()` tạo một background thread/process liên tục cập nhật buffer nội bộ, và `get_latest_state()`/`get_latest_frame()` đọc từ buffer đó.

### 3.4. Tầng 4: Tầng Implementation (`impl/*.py`) - Triển khai Service

**Vai trò:** Các implementation cụ thể tương tác trực tiếp với phần cứng, SDK và dịch vụ bên ngoài.

| Implementation | Interface | Phương thức giao tiếp |
|---|---|---|
| `SdkSportService` | `SportService` | Unitree SDK2 `SportClient` qua DDS |
| `Ros2EchoSportStateService` | `StateService` | Subprocess `ros2 topic echo` + parse YAML |
| `Ros2SportStateService` | `StateService` | Subscriber `rclpy` trong process riêng, giao tiếp qua `multiprocessing.Queue` |
| `SDKSubscriberSportStateService` | `StateService` | Subscriber `rclpy` trong background thread (cùng process) |
| `RpcCameraService` | `CameraService` | Unitree SDK2 `VideoClient` qua DDS |
| `DepthCameraService` | `CameraService` | Intel RealSense `pyrealsense2` pipeline |
| `LocalCameraService` | `CameraService` | OpenCV `VideoCapture` |
| `OpenAISpeakerService` | `SpeakerService` | OpenAI TTS API (streaming async qua `sounddevice`) |
| `PiperSpeakerService` | `SpeakerService` | Piper TTS (offline, local qua `sounddevice`) |
| `AudioCaptureServiceImpl` | `AudioCaptureService` | Vosk ASR + micro `sounddevice`, hotword detection |

---

## 4. Dependency Injection

Project sử dụng **`dependency-injector`** để kết nối các service. Cấu hình tập trung trong `dependencies/__init__.py`.

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

### 4.2. Luồng cấu hình

```
Environment / file .env
        │
        ▼
  ServiceSettings (pydantic-settings)
        │
        ▼
  Go2MiddleLayerContainer.config.from_dict({...})
        │
        ▼
  Mỗi service nhận config tại thời điểm khởi tạo
```

### 4.3. Wiring

Khi ứng dụng khởi động (`server.py`), container được wire tới các module sau để decorator `@inject` + `Provide[...]` hoạt động:

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

Khi một method của controller được gọi, `dependency-injector` tự động resolve `Provide[Go2MiddleLayerContainer.some_service]` thành instance singleton tương ứng.

---

## 5. Pattern Background Service

Tất cả camera service và state service đều tuân theo cùng một pattern:

```
┌─────────────────────────────────────┐
│        Background Thread            │
│                                     │
│  while not stop_event:              │
│    frame = đọc_từ_phần_cứng()      │
│    with lock:                       │
│      buffer = frame                 │
│    sleep(1/fps)                     │
│                                     │
└───────────────┬─────────────────────┘
                │ ghi vào
                ▼
        ┌──────────────┐
        │   Buffer     │ ← được bảo vệ bởi threading.Lock
        │ (frame/state │
        │  mới nhất)   │
        └──────┬───────┘
               │ đọc từ
               ▼
┌──────────────────────────────┐
│     MCP Tool Handler         │
│                              │
│  with lock:                  │
│    return buffer             │
└──────────────────────────────┘
```

Điều này đảm bảo:
- Lệnh gọi MCP tool trả về ngay lập tức (không chờ I/O)
- Dữ liệu mới nhất luôn sẵn sàng
- Truy cập thread-safe vào buffer dùng chung

### 5.1. Lifecycle của Service

Tất cả background service được quản lý trong `server.py` thông qua lifespan context manager của FastAPI:

```
Khởi động App (combined_lifespan)
│
├── wire_container()           ← Khởi tạo DI
├── start_state_background_reader()
├── start_rpc_camera_background_capture(fps=30)
├── start_depth_camera_background_capture(fps=30)
├── start_local_camera_background_capture(fps=30)
├── start_audio_background_capture()
├── Enter lifespan cho mỗi MCP sub-app
│
│   ... server đang chạy ...
│
Tắt App (finally) — thứ tự LIFO, tắt graceful
├── stop_audio_background_capture()
├── stop_local_camera_background_capture()
├── stop_depth_camera_background_capture()
├── stop_rpc_camera_background_capture()
└── stop_state_background_reader()
```

---

## 6. Sport Controller: Logic Di chuyển

`SportController` là use case phức tạp nhất. Nó implement vòng lặp điều khiển dựa trên vận tốc để di chuyển chính xác theo khoảng cách/góc.

### 6.1. Luồng di chuyển

```
Lệnh gọi MCP tool (vd: move_forward(100))
│
├── Hủy lệnh đang chạy (_cancel_current_command)
├── Lấy async lock (chỉ một lệnh di chuyển tại một thời điểm)
├── Đảm bảo robot đang đứng (_ensure_standing_async)
│   ├── Đọc mode hiện tại từ StateService
│   └── Gửi RecoveryStand / BalanceStand nếu cần
│
├── Tính thời gian = khoảng cách / tốc độ
├── Chạy vòng lặp di chuyển (_run_move_loop):
│   │
│   │  while thời_gian_trôi < thời_gian_cần:
│   │    ├── Kiểm tra cancel event (có lệnh mới không?)
│   │    ├── Kiểm tra khoảng cách vật cản qua DepthCameraService (chỉ khi đi tới)
│   │    ├── Gửi Move(vx, vy, vyaw) tới SportService
│   │    └── sleep(loop_interval)
│   │
│   └── Gửi StopMove
│
└── Trả về Response với khoảng cách/góc thực tế đã di chuyển
```

### 6.2. Hủy lệnh (Command Cancellation)

Khi có lệnh di chuyển mới đến trong khi lệnh cũ đang chạy:
1. Lệnh mới set `_cancel_event`
2. Vòng lặp đang chạy phát hiện event và thoát sớm
3. Lệnh mới lấy lock và bắt đầu vòng lặp riêng

Điều này ngăn chặn việc gửi đồng thời các lệnh di chuyển xung đột.

---

## 7. Pipeline Depth Camera

Depth camera service có pipeline xử lý dữ liệu phức tạp nhất:

```
Camera Intel RealSense
│
├── Depth Stream (1280x720, Z16, 30fps)
├── Color Stream (1280x720, BGR8, 30fps)
│
▼ (background thread)
Buffer: composite_frame mới nhất
│
▼ (khi MCP tool được gọi)
│
├── 1. Align depth với color frame
├── 2. Chạy YOLO detection trên ảnh màu (gọi HTTP remote)
├── 3. Chạy captioning trên ảnh màu (tùy chọn, gọi HTTP remote)
│      (bước 1-3 chạy song song qua asyncio.gather)
│
├── 4. Với mỗi vật thể được detect:
│   ├── Trích xuất bounding box từ tọa độ chuẩn hóa
│   ├── Tính depth trong bounding box (box filter + lấy min)
│   ├── Lọc vật thể xa (> 6000mm)
│   └── Ước lượng vị trí 3D bằng camera intrinsics
│       (bù offset 35mm trục X)
│
├── 5. Sắp xếp vật thể theo khoảng cách, thêm hậu tố tên duy nhất
├── 6. Tạo mô tả ngôn ngữ tự nhiên
├── 7. Encode ảnh màu thành JPEG
│
└── Trả về (info_dict, image_bytes)
```

**Dịch vụ remote được sử dụng:**

| Dịch vụ | URL (mặc định) | Mục đích |
|---|---|---|
| YOLO World Detector | `http://<host>:8000/api/dl/yoloworld` | Phát hiện vật thể với danh sách class mở |
| Grounding DINO Detector | `http://<host>:8000/api/dl/grounding-dino` | Phát hiện vật thể zero-shot bằng text prompt |
| Remote Captioner | `http://14.225.217.119:8182/oai-caption` | Mô tả ảnh (hiện đang tắt trong code) |

Các detector YOLO World và Grounding DINO được phục vụ bởi **DL Backend** (`dlbackend/`), một FastAPI service độc lập. Xem [DL Backend](#10-dl-backend-server-phát-hiện-vật-thể) để biết chi tiết.

---

## 8. State Service: Hai Implementation

Project cung cấp hai cơ chế đọc trạng thái robot, cả hai chạy đồng thời:

### 8.1. Implementation Echo (`Ros2EchoSportStateService`)

```
Background Thread
│
├── Spawn: ros2 topic echo /lf/sportmodestate --qos-reliability best_effort
├── Đọc stdout từng dòng
├── Gom dòng cho đến dấu phân cách "---"
├── Parse khối YAML → RobotState.sportmodestate
└── Lưu vào buffer
```

**Ưu điểm:** Không cần dependency rclpy trong process chính. Cách tiếp cận subprocess đơn giản.
**Nhược điểm:** Chậm hơn, phụ thuộc vào CLI `ros2` có sẵn.

### 8.2. Implementation ROS2 Node (`Ros2SportStateService`)

```
Process Chính                   Process Riêng
│                               │
├── mp.Queue ◄─── state ──── ROS2 Subscriber Node
├── mp.Event (tín hiệu dừng)   │
│                               ├── rclpy.init()
├── Reader Thread               ├── Tạo SportStateSubscriber
│   └── queue.get() → buffer    ├── executor.spin()
│                               └── Khi nhận message: queue.put(state)
```

**Ưu điểm:** ROS2 subscriber native, độ trễ thấp hơn, đáng tin cậy hơn.
**Nhược điểm:** Cần rclpy và ROS2 message types trong process riêng để tránh vấn đề GIL.

Cả hai service đều được khởi động khi ứng dụng bắt đầu. Sport controller sử dụng `state_service_using_ros2` cho việc kiểm tra mode realtime, trong khi MCP tools expose cả hai tùy chọn.

---

## 9. Speaker Service: TTS & Phát âm thanh

Speaker service cho phép robot nói text và phát các file âm thanh đã ghi sẵn.

### 9.1. Kiến trúc

```
Lệnh gọi MCP tool (vd: speak_text("Xin chào"))
│
├── SpeakerController.speak_text(text, interrupt)
│   └── SpeakerService.aspeak(text, interrupt)
│       ├── TTS engine sinh ra audio chunks (streaming)
│       ├── Resampler chuyển đổi sang sample rate output
│       └── sounddevice.OutputStream phát âm thanh
│
├── SpeakerController.play_recorded_audio(audio_name, interrupt)
│   ├── Tra cứu đường dẫn file: {SPEAKER_AUDIO_DIR}/{audio_name}.wav
│   └── SpeakerService.aplay_file(file_path, interrupt)
│       ├── soundfile đọc file WAV theo chunks
│       ├── Resampler chuyển đổi sang sample rate output
│       └── sounddevice.OutputStream phát âm thanh
│
└── SpeakerController.interrupt()
    └── SpeakerService.interrupt_all_task()
```

### 9.2. Hai implementation TTS

| Implementation | Base Class | TTS Engine | Trường hợp sử dụng |
|---|---|---|---|
| `OpenAISpeakerService` | `AsyncSpeakerDeviceBase` | OpenAI TTS API (streaming) | TTS chất lượng cao, qua cloud |
| `PiperSpeakerService` | `SyncSpeakerDeviceBase` | Piper (model ONNX local) | TTS offline, độ trễ thấp |

Implementation đang hoạt động được chọn qua biến môi trường `SPEAKER_TTS_ENGINE` (`openai` hoặc `piper`), sử dụng `Selector` provider của `dependency-injector`.

### 9.3. Pipeline âm thanh

```
TTS Engine (24kHz mono)
│
├── Resampler (soxr): 24kHz → 48kHz (sample rate output)
├── _normalize_audio: chuẩn hóa sang phạm vi float32
├── _adapt_channels: khớp số kênh với output stream (mono ↔ stereo)
│
└── sounddevice.OutputStream.write(chunk)
```

### 9.4. Âm thanh ghi sẵn (Enum RecordedAudio)

Các clip âm thanh có sẵn được định nghĩa qua enum `RecordedAudio`:

| Giá trị | File |
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

**Script tải:** Chạy `python scripts/download_recorded_audio.py` để tải các file WAV tiếng chó sủa từ OpenGameArt.org. Xem `docs/features.md` §7.4 và `src/resources/sound/dog/SOURCES.md`.

---

## 10. DL Backend (Server phát hiện vật thể)

Thư mục `dlbackend/` chứa một **FastAPI server độc lập** cho phát hiện vật thể zero-shot, được thiết kế để thay thế server phát hiện bên ngoài dùng bởi pipeline depth camera.

### 10.1. Kiến trúc

```
dlbackend/
├── server.py              # FastAPI app, endpoint /api/dl/*, load model
├── models.py              # Pydantic request/response schemas
├── default_classes.py     # ~400 class vật thể mặc định (trong nhà, ngoài trời, tự nhiên, tổng quát)
├── detectors/
│   ├── base.py            # BaseDetector ABC (detect, is_ready)
│   ├── yolo_world.py      # YOLOWorldDetector (ultralytics YOLOWorld)
│   └── grounding_dino.py  # GroundingDINODetector (HF transformers)
├── .env                   # Cấu hình model
├── requirements.txt       # Dependency riêng
├── nginx.conf             # Cấu hình nginx reverse proxy cho RunPod
├── Dockerfile             # Docker image với CUDA + nginx
├── start.sh               # Script khởi động RunPod
└── README.md              # Tài liệu sử dụng
```

### 10.2. Pipeline phát hiện

```
Client (RemoteYOLOv8Detector)
│
├── POST /api/dl/yoloworld
│   └── YOLOWorldDetector
│       ├── model.set_classes(classes)
│       ├── model.predict(image)
│       └── Chuyển đổi xyxy → xywh (tọa độ pixel)
│
├── POST /api/dl/grounding-dino
│   └── GroundingDINODetector
│       ├── Nối classes → "person . chair . table ."
│       ├── processor(image, text) → model(**inputs)
│       ├── post_process_grounded_object_detection()
│       └── Chuyển đổi boxes → xywh (tọa độ pixel)
│
└── GET /api/dl/health
```

### 10.3. API Contract

Cả hai endpoint nhận cùng request và trả về cùng format response:

**Request:**
```json
{
  "image_b64": "<JPEG/PNG mã hóa base64>",
  "classes": ["person", "chair"]
}
```

`classes` là tùy chọn — nếu bỏ qua, ~400 class mặc định (vật thể trong nhà + ngoài trời + tự nhiên + tổng quát) sẽ được dùng.

**Response:**
```json
[
  { "class_name": "person", "xywh": [320.5, 240.0, 80.0, 160.0], "confidence": 0.92 }
]
```

- `xywh`: bounding box dạng `[tâm_x, tâm_y, rộng, cao]` tính bằng pixel
- `confidence`: độ tin cậy phát hiện

### 10.4. Cấu hình

Model được cấu hình qua `dlbackend/.env`:

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `YOLO_WORLD_MODEL` | `yolov8x-worldv2.pt` | Phiên bản model YOLO-World |
| `GROUNDING_DINO_MODEL` | `IDEA-Research/grounding-dino-tiny` | ID model Grounding DINO trên HuggingFace |

### 10.5. Triển khai

DL backend được thiết kế để chạy trên server GPU (vd. RunPod) tách biệt với server GO2 chính. Xem `dlbackend/README.md` để biết hướng dẫn triển khai.

Tích hợp với server chính chỉ cần cập nhật `DEFAULT_REMOTE_DETECTOR_URL` trong `.env` chính:

```env
DEFAULT_REMOTE_DETECTOR_URL=https://<host>/api/dl/yoloworld
# hoặc
DEFAULT_REMOTE_DETECTOR_URL=https://<host>/api/dl/grounding-dino
```
