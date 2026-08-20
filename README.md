# GO2 Sport Control

FastAPI + MCP server điều khiển chuyển động (sport) và đọc trạng thái (state) của robot Unitree GO2W.

Tách ra từ `go2_middle_layer/`, chỉ giữ hai luồng đó. **`go2_middle_layer/` giờ chỉ là thư mục tham khảo** — code trong `src/` không import gì từ nó.

## Kiến trúc

Giữ nguyên phân layer của repo gốc:

```
src/
├── server.py              FastAPI app, lifespan, mount MCP, /health + /status
├── service_registry.py    registry trạng thái dịch vụ, nguồn của /status
├── paths.py               resolve path theo src/ (độc lập cwd)
│
├── mcps/                  Lớp giao tiếp — định nghĩa MCP tool
│   ├── configs.py           cấu hình logging
│   ├── sport.py             stand_up, move_forward, turn_left, ...
│   └── sportstate.py        get_sport_mode_state
│
├── usecases/              Lớp nghiệp vụ — điều phối, không biết SDK
│   ├── sport_controller.py  vòng lặp move, ensure_standing, huỷ lệnh đang chạy
│   └── state_controller.py  đọc state mới nhất
│
├── interfaces/            Hợp đồng trừu tượng (ABC)
│   ├── sport.py             SportService.handle()
│   └── state.py             StateService.start/stop/get_latest_state()
│
├── impl/                  Lớp hiện thực — chỗ duy nhất chạm vào SDK/ROS2
│   ├── sdk_sport/           điều khiển qua unitree_sdk2py
│   │   ├── sdk_sport_service.py
│   │   └── sdk_sport_service_stub.py     dùng khi thiếu unitree_sdk2py
│   ├── state/               đọc state
│   │   ├── ros2_state_service.py         rclpy trong process riêng (đang dùng)
│   │   ├── ros2_state_service_stub.py    dùng khi thiếu rclpy
│   │   └── sdk_state_service.py          biến thể, chưa nối vào DI
│   └── device_watcher/      tự khởi động lại dịch vụ khi robot boot sau server
│
├── models/                Kiểu dữ liệu
│   ├── response.py          Response chung
│   ├── sport_option.py      enum lệnh + bảng API ID + mã lỗi
│   ├── sport_request.py     SportRequest
│   └── state.py             RobotState, SportModeEnum, GaitTypeEnum
│
└── dependencies/          DI container (dependency-injector) + settings
```

Chiều phụ thuộc một chiều: `mcps → usecases → interfaces ← impl`. `usecases` chỉ biết `interfaces`, không biết `impl` — `dependencies/` là chỗ duy nhất nối hai bên.

### Cơ chế stub

`dependencies/_lazy_class()` nạp module lười, kèm fallback. Thiếu thư viện thì tự chuyển sang bản stub thay vì crash:

| Thiếu | Chuyển sang | Hậu quả |
|---|---|---|
| `unitree_sdk2py` | `SdkSportServiceStub` | mọi lệnh sport trả 503 |
| `rclpy` | `Ros2SportStateServiceStub` | `get_latest_state()` trả None |

Server vẫn boot và `/status` báo rõ dịch vụ nào hỏng vì lý do gì.

## Cần cài gì

Ba thứ, cài theo đúng thứ tự:

**1. Thư viện C CycloneDDS** — không có wheel cho aarch64 nên phải build từ nguồn:

```bash
git clone -b releases/0.10.x https://github.com/eclipse-cyclonedds/cyclonedds
cd cyclonedds && mkdir -p build install && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=../install -DCMAKE_BUILD_TYPE=Release
cmake --build . --target install -j$(nproc)
export CYCLONEDDS_HOME=$(cd ../install && pwd)
```

**2. unitree_sdk2_python** — cần `CYCLONEDDS_HOME` từ bước trên:

```bash
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
pip install -e ./unitree_sdk2_python
```

**3. Các gói Python còn lại:**

```bash
pip install -r src/requirements.txt
```

`rclpy` **không** nằm trong requirements — nó không tồn tại trên PyPI, chỉ đi kèm bản cài ROS2 qua apt. Thiếu nó thì state service chạy stub, phần điều khiển vẫn hoạt động bình thường.

## Cấu hình

```bash
cp .env.example .env
```

Biến quan trọng nhất là `STATE_NETWORK_INTERFACE` — tên cổng Ethernet nối sang robot, dùng cho **cả** sport service lẫn state service:

```
STATE_NETWORK_INTERFACE=end0
```

Trên board OrangePi tên là `end0` (driver Allwinner `dwmac-sunxi`), **không phải** `eth0` hay `enp2s0` như tài liệu Unitree ghi.

## Chạy

```bash
make run                  # hoac: python src/server.py
```

Server lên ở `http://0.0.0.0:8001`. Nếu cổng bận, tự thử 8002, 8003... tối đa 10 cổng.

| Endpoint | Mục đích |
|---|---|
| `GET /health` | sống hay chết |
| `GET /status` | dịch vụ nào available, lỗi gì |
| `/sport/mcp` | MCP điều khiển chuyển động |
| `/sport_state/mcp` | MCP đọc trạng thái |

## Test

Cần server đang chạy:

```bash
make test-sport           # cong cu MCP dieu khien
make test-sport-state     # doc trang thai
```

> **Cảnh báo:** `test_sport_mcp_tools.py` phát lệnh làm **robot chuyển động thật**. Kiểm tra không gian xung quanh trước khi chạy.

## Khác biệt so với `go2_middle_layer/`

| | Thay đổi |
|---|---|
| Layer bỏ | camera (rpc/depth/local), speaker/TTS, audio capture, YOLO |
| `sport_controller` | bỏ phụ thuộc `depth_camera_service`; nhánh tránh vật cản vẫn còn nhưng không được kích hoạt |
| `impl/state/` | bỏ `echo_state_service` (đã deprecated, cần `ros2 topic echo` CLI) |
| Mặc định interface | `eth0` → `end0` |
| `service_registry` | còn 3 mục: `sport`, `state_ros2`, `device_watcher` |
| `requirements.txt` | 30 gói → 10 gói, bỏ `rclpy` |
