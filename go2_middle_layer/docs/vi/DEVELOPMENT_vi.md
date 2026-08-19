# Hướng dẫn phát triển

Tài liệu này cung cấp ngữ cảnh cho developer làm việc với GO2 Middle Layer. Bao gồm chế độ bypass thiết bị, tắt máy graceful, xử lý port, và các mẫu kiến trúc.

---

## 1. Chạy không cần đầy đủ phần cứng GO2 (Bypass Mode)

Server được thiết kế để **chạy trên mọi máy** — kể cả không có robot GO2, camera RealSense, ROS2 hay phần cứng khác. Khi dependency hoặc thiết bị tùy chọn không có sẵn, server dùng **stub implementations** và tiếp tục chạy. Các endpoint MCP bị ảnh hưởng trả về "not available" thay vì crash.

### 1.1 Các dependency tùy chọn & Stub

| Service | Dependency bắt buộc | Khi không có | Vị trí Stub |
|---------|---------------------|--------------|-------------|
| Depth camera | `pyrealsense2` | Chưa cài | `impl/depth_camera_service_stub.py` |
| ROS2 state | `rclpy` | Chưa cài | `impl/ros2_state_service_stub.py` |
| RPC camera | `unitree_sdk2py` | Chưa cài | `impl/rpc_camera_service_stub.py` |
| Sport control | `unitree_sdk2py` | Chưa cài | `impl/sdk_sport_service_stub.py` |
| Echo state | `ros2` CLI | Không có trong PATH | Log warning, trả về `None` |
| Local camera | OpenCV + USB cam | Không tìm thấy thiết bị | Log warning, trả về `None` |
| Audio capture | `sounddevice` + `vosk` | Lỗi thiết bị | Log error, trả về `[]` |

### 1.2 Cơ chế Bypass

Trong `dependencies/__init__.py`, các service được import bằng `try/except`:

```python
try:
    from impl.depth_camera_service import DepthCameraService
except ImportError:
    from impl.depth_camera_service_stub import DepthCameraServiceStub as DepthCameraService
```

- **Lỗi khi import** (vd. `pyrealsense2` chưa cài) → dùng stub.
- **Lỗi runtime** (vd. không tìm thấy camera) → service thật xử lý gracefully (log + trả về `None`).

### 1.3 Thiết lập tối thiểu cho phát triển

Chỉ cần:

```bash
conda create -n go2 python=3.12 -y && conda activate go2
make install                    # Cài dependency + pytest
make run                       # Chạy server (từ thư mục gốc project)
```

Hoặc thủ công:

```bash
cd src && pip install -r requirements.txt
pip install pytest pytest-asyncio
python src/server.py
```

Server sẽ khởi động. Các endpoint như `/sport/mcp`, `/camera/mcp`, `/depth_camera/mcp`, `/sport_state/mcp` sẽ trả về "not available" cho đến khi cài SDK/phần cứng tương ứng.

### 1.4 Bật đầy đủ chức năng

| Tính năng | Cài đặt / Kết nối |
|-----------|-------------------|
| Điều khiển robot & RPC camera | `unitree_sdk2_python` + mạng tới robot |
| Depth camera | `conda install -c conda-forge pyrealsense2` + RealSense |
| Phát hiện vật thể (depth cam) | Chạy `dlbackend/` trên server GPU, đặt `DEFAULT_REMOTE_DETECTOR_URL` |
| Robot state | ROS2 + `rclpy` hoặc `ros2 topic echo` |
| Local camera | USB camera (device ID trong `LOCAL_CAMERA_DEVICE_ID`) |
| Lệnh giọng nói | `sounddevice`, `vosk` + microphone |

---

## 2. Xử lý Port

### 2.1 Port Fallback

Mặc định, nếu port yêu cầu (vd. 8001) đã được dùng, server **thử port tiếp theo** (8002, 8003, … tối đa 10 lần).

```bash
python src/server.py                    # Dùng 8001, hoặc 8002 nếu 8001 bận
python src/server.py --port 9000        # Dùng 9000, hoặc 9001, 9002, …
python src/server.py --no-port-fallback # Thất bại nếu port đang dùng (không fallback)
```

### 2.2 Biến môi trường

- `PORT` — port mặc định (mặc định: 8001)
- `UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN` — giây chờ tắt máy graceful (mặc định: 10)

---

## 3. Graceful Shutdown

Khi server nhận SIGTERM hoặc SIGINT (vd. Ctrl+C), nó:

1. Ngừng nhận kết nối mới
2. Chờ các request đang xử lý (tối đa `timeout_graceful_shutdown` giây)
3. Dọn dẹp services theo **thứ tự ngược startup** (LIFO):
   - audio_capture → local_camera → depth_camera → rpc_camera → state_background_reader
4. Thoát

### 3.1 Thứ tự Shutdown

Các service dừng theo thứ tự ngược startup để giải phóng tài nguyên phụ thuộc trước.

### 3.2 Xử lý lỗi khi Shutdown

Mỗi lệnh stop service được bọc trong `_stop_service()`, bắt exception và log mà không chặn các cleanup khác. Một service lỗi không ngăn các service khác dừng.

### 3.3 Cấu hình

```bash
python src/server.py --timeout-graceful-shutdown 15
# hoặc
UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN=20 python src/server.py
```

---

## 4. Tóm tắt kiến trúc

### 4.1 Luồng 4 tầng

```
MCP (mcps/*) → Use Cases (usecases/*) → Interfaces (interfaces/*) ← Implementations (impl/*)
```

- **MCP**: Định nghĩa tool, chuyển xuống controller
- **Use cases**: Business logic, điều phối
- **Interfaces**: ABCs (hợp đồng)
- **Implementations**: Service cụ thể (SDK, phần cứng)

### 4.2 Stub Implementations

Stub nằm trong `impl/*_stub.py` và implement cùng interface với service thật. Chúng:

- `start()` / `stop()` — no-op
- `get_latest_frame()` / `get_latest_state()` — trả về `None`
- Log warning khi init để developer biết tính năng bị tắt

### 4.3 Thêm service tùy chọn mới

1. Tạo `impl/xxx_service.py` (implementation thật)
2. Tạo `impl/xxx_service_stub.py` (stub)
3. Trong `dependencies/__init__.py`:
   ```python
   try:
       from impl.xxx_service import XxxService
   except ImportError:
       from impl.xxx_service_stub import XxxServiceStub as XxxService
   ```
4. Đăng ký trong `Go2MiddleLayerContainer`
5. Thêm start/stop vào lifespan của `server.py`

---

## 5. Tham chiếu file

| Đường dẫn | Mục đích |
|-----------|----------|
| `Makefile` | Server, tests, lint, format, install targets |
| `src/server.py` | FastAPI app, lifespan, port fallback, graceful shutdown |
| `src/dependencies/__init__.py` | DI container, đăng ký service, bypass imports |
| `src/impl/*_stub.py` | Stub implementations cho services tùy chọn |
| `src/interfaces/*.py` | Abstract base classes |
| `tests/` | Integration tests (pytest; cần server đang chạy) |
| `docs/architecture.md` | Kiến trúc chi tiết |
| `docs/features.md` | API reference |
| `docs/DEVELOPMENT.md` | File gốc tiếng Anh — bypass mode, port, shutdown, Makefile |
| `CLAUDE.md` | Quick reference cho AI assistants |
| `dlbackend/` | DL Backend — server phát hiện vật thể YOLO-World & Grounding DINO |
| `dlbackend/README.md` | Hướng dẫn cài đặt, triển khai, API của DL Backend |

---

## 6. Makefile

Project cung cấp Makefile cho các tác vụ thường dùng. Chạy `make help` để xem danh sách targets.

### 6.1 Server

| Target | Mô tả |
|--------|-------|
| `make run` | Chạy server foreground (port 8001) |
| `make run-bg` | Chạy server background |
| `make kill-server` | Kill process trên port 8001 |

### 6.2 Tests (cần server chạy trên port 8001, trừ `test-yolo`)

| Target | Mô tả |
|--------|-------|
| `make test` / `make test-all` | Chạy tất cả pytest tests |
| `make test-sport` | Sport MCP tools |
| `make test-sport-state` | Sport state |
| `make test-rpc-cam` | RPC camera |
| `make test-depth-cam` | Depth camera |
| `make test-local-cam` | Local camera |
| `make test-speaker` | Speaker/TTS |
| `make test-audio-capture` | Audio capture |
| `make test-yolo` | YOLO detector (không cần server) |

### 6.3 Chất lượng code

| Target | Mô tả |
|--------|-------|
| `make lint` | Chạy ruff check |
| `make format` | Chạy black + ruff format |

### 6.4 Thiết lập

| Target | Mô tả |
|--------|-------|
| `make install` | Cài dependencies + pytest |
| `make clean` | Xóa `__pycache__`, `.pytest_cache` |

---

## 7. Lint

Trước khi commit, chạy:

```bash
make lint
make format
```

Hoặc thủ công:

```bash
black src/
ruff check src/
```

---

## 8. Các tác vụ thường dùng

### Kill process trên port 8001

```bash
make kill-server
# hoặc: lsof -ti :8001 | xargs kill -9
```

### Chạy server với log chi tiết

```bash
LOG_LEVEL=DEBUG python src/server.py
```

### Test health endpoint

```bash
curl http://localhost:8001/health
```

### Chạy bộ test cụ thể

```bash
make test-sport        # pytest
make run-sport         # Chạy script test trực tiếp (không dùng pytest)
```
