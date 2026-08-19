# Tính năng & Tham chiếu API

## 1. Tổng quan

### 1.1 Mô tả dịch vụ

GO2 Middle Layer expose **7 dịch vụ MCP (Model Context Protocol)**, mỗi dịch vụ được mount trên đường dẫn riêng dưới một FastAPI server duy nhất. Mọi MCP tool đều trả về object `Response` thống nhất.

#### 1.1.1 Format Response thống nhất

Tất cả endpoint trả về:

```json
{
  "success": true,
  "message": "Mô tả kết quả dễ đọc",
  "data": "<payload — khác nhau tùy endpoint>",
  "code": 200,
  "extra_data": null
}
```

## 2. Điều khiển vận động (Sport Control) — `/sport/mcp`

Điều khiển di chuyển và các hành động của robot thông qua Unitree SDK2 sport client.

### 2.1 Các Tool

#### 2.1.1 `stop_move()`
Dừng mọi chuyển động hiện tại.

- **Input:** Không
- **Output:** `Response` với thông báo xác nhận

#### 2.1.2 `stand_up()`
Làm robot đứng lên. Tự động khôi phục từ trạng thái nằm hoặc damping trước.

- **Input:** Không
- **Output:** `Response` với thông báo xác nhận

#### 2.1.3 `stand_down()`
Làm robot nằm xuống. Tự động chuyển qua trạng thái đứng nếu cần.

- **Input:** Không
- **Output:** `Response` với thông báo xác nhận

#### 2.1.4 `move_forward(distance: int)`
Di chuyển thẳng về phía trước.

- **Input:** `distance` — khoảng cách tính bằng centimet (giới hạn `[0, 300]`)
- **Output:** `Response` với thông báo bao gồm khoảng cách thực tế đã di chuyển
- **Hành vi:** Sử dụng depth camera để kiểm tra vật cản. Dừng lại nếu phát hiện vật cản gần hơn 400mm.

#### 2.1.5 `move_backward(distance: int)`
Di chuyển thẳng về phía sau.

- **Input:** `distance` — khoảng cách tính bằng centimet (giới hạn `[0, 300]`)
- **Output:** `Response` với thông báo bao gồm khoảng cách thực tế đã di chuyển

#### 2.1.6 `turn_left(angle: int)`
Quay trái tại chỗ.

- **Input:** `angle` — góc tính bằng độ (giới hạn `[0, 180]`)
- **Output:** `Response` với thông báo bao gồm số độ thực tế đã quay

#### 2.1.7 `turn_right(angle: int)`
Quay phải tại chỗ.

- **Input:** `angle` — góc tính bằng độ (giới hạn `[0, 180]`)
- **Output:** `Response` với thông báo bao gồm số độ thực tế đã quay

#### 2.1.8 `step_to_left(distance: int)`
Bước ngang sang trái.

- **Input:** `distance` — khoảng cách tính bằng centimet (giới hạn `[0, 300]`)
- **Output:** `Response` với thông báo bao gồm khoảng cách thực tế đã di chuyển

#### 2.1.9 `step_to_right(distance: int)`
Bước ngang sang phải.

- **Input:** `distance` — khoảng cách tính bằng centimet (giới hạn `[0, 300]`)
- **Output:** `Response` với thông báo bao gồm khoảng cách thực tế đã di chuyển

#### 2.1.10 `move_to_target_position(angle: float, distance: float)`
Quay hướng về mục tiêu rồi đi thẳng tới đó, kết hợp quay và đi tới trong một lần gọi.

- **Input:**
  - `angle` — góc tính bằng độ (`[-180, 180]`). `0` = phía trước, dương = bên trái, âm = bên phải
  - `distance` — khoảng cách tính bằng centimet (giới hạn `[0, 300]`)
- **Output:** `Response` với thông báo kết hợp kết quả quay + di chuyển
- **Hành vi:** Sử dụng depth camera để kiểm tra vật cản trong giai đoạn đi tới.

### 2.2 Thông số chính sách di chuyển mặc định

| Thông số             | Giá trị    | Mô tả                       |
|----------------------|------------|------------------------------|
| `move_speed_mps`     | 0.4 m/s    | Tốc độ di chuyển thẳng      |
| `yaw_speed_rps`      | 0.5 rad/s  | Tốc độ quay                 |
| `loop_interval_sec`  | 0.01s      | Chu kỳ vòng lặp điều khiển  |
| `command_timeout_sec`| 3.0s       | Timeout lệnh SDK            |
| `retry_count`        | 1          | Số lần thử lại khi lệnh SDK thất bại |

## 3. Trạng thái vận động (Sport State) — `/sport_state/mcp`

Đọc trạng thái realtime của robot (vị trí, vận tốc, IMU, lực chân, v.v.).

### 3.1 Tool: `get_sport_mode_state()`
Lấy trạng thái mới nhất của robot.

- **Input:** Không
- **Output:** `Response` trong đó `data` là `RobotState`:

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
    "range_obstacle": [trước, phải, sau, trái],
    "foot_force": [trước_trái, trước_phải, sau_trái, sau_phải],
    "foot_position_body": [12 số thực],
    "foot_speed_body": [12 số thực]
  },
  "lowstate": { }
}
```
Có hai implementation:

**`get_sport_mode_state_using_echo()`**: Đọc trạng thái qua subprocess `ros2 topic echo`.
**`get_sport_mode_state_using_ros2()`**: Đọc trạng thái bằng ROS2 subscriber node native (rclpy), chạy trong process riêng.

### 3.2 Giá trị Sport Mode

| Giá trị | Chế độ               |
|---------|----------------------|
| 0       | Nghỉ (Idle)          |
| 1       | Đang đứng (Standing) |
| 2       | Đi (theo vận tốc)    |
| 3       | Đi (theo vị trí)     |
| 4       | Đi (theo đường dẫn)  |
| 5       | Ngồi xuống           |
| 6       | Đứng lên             |
| 7       | Damping (thả lỏng)   |
| 8       | Khôi phục            |
| 9       | Lộn ngửa             |
| 10      | Nhảy xoay            |
| 11      | Thẳng tay            |
| 12      | Nhảy 1               |
| 13      | Nhảy 2               |

### 3.3 Giá trị Gait Type (Kiểu dáng đi)

| Giá trị | Kiểu dáng đi         |
|---------|----------------------|
| 0       | Nghỉ                |
| 1       | Trot walking (đi bộ) |
| 2       | Trot running (chạy)  |
| 3       | Leo cầu thang        |
| 4       | Trot vượt chướng ngại|

---

## 4. Camera Robot (RPC Camera) — `/camera/mcp`

Chụp ảnh từ camera trước tích hợp trên robot qua Unitree SDK2 `VideoClient`.

**Tool: `capture_image()`**:
Lấy frame mới nhất từ buffer capture nền.
- **Input:** Không
- **Output:** `Response` trong đó `data` là **chuỗi ảnh mã hóa base64** (format phụ thuộc SDK, thường là JPEG)
- **Trường hợp lỗi:**
  - `code: 425` — Buffer trống, chưa có frame nào được capture
  - `code: 400` — Capture frame thất bại

---

## 5. Depth Camera — `/depth_camera/mcp`

Chụp frame màu và depth từ camera Intel RealSense, chạy YOLO phát hiện vật thể, ước lượng vị trí 3D của các vật thể được phát hiện, và tạo mô tả cảnh bằng ngôn ngữ tự nhiên.

### 5.1 Tool: `capture_image()`
Lấy frame depth camera đã xử lý mới nhất.

- **Input:** Không
- **Output:** `Response` trong đó:
  - `data` — ảnh JPEG mã hóa base64 (frame màu)
  - `extra_data` — thông tin phân tích chi tiết:

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

### 5.2 Mô tả ngôn ngữ tự nhiên

Field `natural_language_description` cung cấp tóm tắt cảnh dạng văn bản thân thiện với LLM:
- Timestamp của lần chụp
- Mô tả ảnh (nếu captioner được bật)
- Với mỗi vật thể gần: khoảng cách tính bằng centimet và góc so với tâm (trái/phải)
- Các vật thể xa (>6m) được liệt kê theo tên
- Ghi chú an toàn về giới hạn góc nhìn của camera

### 5.3 Cấu hình Camera

| Thông số                    | Giá trị       |
|-----------------------------|--------------|
| Độ phân giải depth          | 1280 x 720   |
| Độ phân giải màu            | 1280 x 720   |
| FPS                         | 30           |
| Ngưỡng tầm xa              | 6000 mm      |
| Ngưỡng tránh vật cản       | 400 mm       |

---

## 6. Camera Local — `/local_camera/mcp`

Chụp ảnh từ camera kết nối local (webcam USB hoặc tương tự) sử dụng OpenCV.

### 6.1 Tool: `capture_image()`
Lấy frame mới nhất từ buffer capture nền.

- **Input:** Không
- **Output:** `Response` trong đó `data` là **chuỗi ảnh PNG mã hóa base64**
- **Trường hợp lỗi:**
  - `code: 425` — Buffer trống, chưa có frame nào được capture
  - `code: 400` — Capture frame thất bại

### 6.2 Cấu hình Camera

| Thông số   | Giá trị       |
|------------|--------------|
| Độ phân giải | 1280 x 720  |
| FPS        | 30           |
| Device ID  | Cấu hình qua biến môi trường `LOCAL_CAMERA_DEVICE_ID` (mặc định: `0`) |

---

## 7. Speaker — `/speaker/mcp`

Điều khiển text-to-speech (TTS) và phát âm thanh ghi sẵn qua loa của robot.

### 7.1 Các Tool

#### 7.1.1 `speak_text(text: str, interrupt: bool = False)`
Nói text ra loa bằng TTS. Robot sẽ chuyển đổi text thành giọng nói và phát qua loa.

- **Input:**
  - `text` — văn bản cần nói
  - `interrupt` — nếu `True`, dừng mọi âm thanh đang phát trước khi nói (mặc định: `False`)
- **Output:** `Response` với thông báo xác nhận

#### 7.1.2 `recorded_audio_speak(audio_name: RecordedAudio, interrupt: bool = False)`
Phát một clip âm thanh ghi sẵn qua loa robot.

- **Input:**
  - `audio_name` — một trong: `bark`, `happy`, `sad`, `alert`, `greeting`, `goodbye`, `acknowledge`, `error`, `confused`
  - `interrupt` — nếu `True`, dừng mọi âm thanh đang phát trước khi phát (mặc định: `False`)
- **Output:** `Response` với thông báo xác nhận
- **Trường hợp lỗi:**
  - File âm thanh không tìm thấy — trả về `success: false` kèm thông báo liệt kê các tên hợp lệ

#### 7.1.3 `stop_speaking()`
Dừng tất cả âm thanh đang phát ngay lập tức.

- **Input:** Không
- **Output:** `Response` với thông báo xác nhận

### 7.2 Cấu hình TTS Engine

Engine TTS đang hoạt động được chọn qua biến môi trường `SPEAKER_TTS_ENGINE`:

| Engine | Giá trị | Mô tả |
|--------|---------|-------|
| OpenAI TTS | `openai` (mặc định) | TTS chất lượng cao, streaming qua OpenAI API |
| Piper TTS | `piper` | TTS offline, chạy local bằng model ONNX |

### 7.3 Cấu hình Speaker

| Thông số | Biến môi trường | Mặc định | Mô tả |
|----------|----------------|----------|-------|
| TTS Engine | `SPEAKER_TTS_ENGINE` | `openai` | Engine TTS: `openai` hoặc `piper` |
| Device ID | `SPEAKER_DEVICE_ID` | `None` (mặc định hệ thống) | ID thiết bị âm thanh đầu ra |
| Sample Rate | `SPEAKER_SAMPLE_RATE` | `48000` | Sample rate đầu ra (Hz) |
| Block Size | `SPEAKER_BLOCK_SIZE` | `1024` | Kích thước block âm thanh |
| Channels | `SPEAKER_CHANNELS` | `1` | Số kênh đầu ra |
| OpenAI API Key | `OPENAI_API_KEY` | `""` | API key cho OpenAI TTS |
| OpenAI Base URL | `OPENAI_BASE_URL` | `None` | URL base tùy chỉnh cho OpenAI API |
| TTS Model | `TTS_MODEL` | `gpt-4o-mini-tts` | Tên model TTS OpenAI |
| TTS Voice | `TTS_VOICE` | `coral` | Tên giọng nói OpenAI TTS |
| Piper Model | `DEFAULT_PIPER_MODEL` | `en_US-lessac-medium.onnx` | File model Piper ONNX |
| Thư mục Audio | `SPEAKER_AUDIO_DIR` | `/opt/doggi/data/audio` | Thư mục chứa các file `.wav` ghi sẵn |
| Chunk Write Timeout | `SPEAKER_CHUNK_WRITE_TIMEOUT` | `10.0` | Thời gian tối đa chờ ghi một chunk âm thanh (giây) |
| Lock Acquire Timeout | `SPEAKER_LOCK_ACQUIRE_TIMEOUT` | `5.0` | Thời gian tối đa chờ lấy khóa speaker (giây) |
| TTS Speed | `TTS_SPEED` | `1.5` | Tốc độ giọng nói OpenAI TTS |
| TTS Chunk Size | `TTS_CHUNK_SIZE` | `2048` | Kích thước chunk PCM streaming (bytes) |

### 7.4 Tải Âm thanh Ghi sẵn

Các file WAV cho `recorded_audio_speak` có thể tải bằng script có sẵn. Thư mục mặc định là `resources/sound/dog` (tương đối với `src/`).

```bash
python scripts/download_recorded_audio.py
```

Script giải nén **tiếng chó sủa, gầm, rên** từ pack dog.7z của OpenGameArt (CC0). Cần `py7zr`. Dùng `--force` để ghi đè, `--fallback` nếu không có py7zr. Xem `src/resources/sound/dog/SOURCES.md`.

---

## 8. Audio Capture — `/audio_capture/mcp`

Thu âm lệnh giọng nói từ micro bằng hotword detection và ASR. Hỗ trợ hai engine chọn qua `AUDIO_CAPTURE_ENGINE`:

- **`vosk`** (mặc định) — ASR offline dùng model Vosk local. Không cần API key.
- **`deepgram`** — ASR cloud qua Deepgram Flux streaming WebSocket. Cần `DEEPGRAM_API_KEY`.

Capture nền lắng nghe hotword (vd. "hello"), sau đó chuyển giọng nói tiếp theo thành các task text. Cũng hỗ trợ transcribe file âm thanh bên ngoài (vd. tin nhắn thoại Telegram) mà không cần micro.

### 8.1 Các Tool

#### 8.1.1 `get_audio_tasks()`
Trả về tất cả task giọng nói thu được kể từ lần gọi trước. Mỗi task là một lệnh được nói sau hotword hoặc transcribe từ audio bên ngoài. Hàng đợi được làm trống sau mỗi lần gọi.

- **Input:** Không
- **Output:** `Response` với `data` = danh sách chuỗi lệnh đã transcribe (danh sách rỗng khi không có task mới)
- **Trường hợp lỗi:**
  - Dịch vụ không khả dụng — trả về `success: false`, `code: 503` khi audio capture không có (không có micro, chưa cài Vosk, hoặc lỗi thiết bị)

#### 8.1.2 `transcribe_audio(audio_base64, audio_format)`
Transcribe file âm thanh bên ngoài (vd. tin nhắn thoại Telegram). Nhận audio data mã hóa base64 và gợi ý định dạng. Text transcribe được trả về ngay và cũng append vào hàng đợi task (lấy qua `get_audio_tasks`). Không cần micro — chỉ cần Vosk model.

- **Input:**
  - `audio_base64` (str, bắt buộc) — bytes file audio mã hóa base64
  - `audio_format` (str, mặc định `"ogg"`) — gợi ý định dạng audio (ogg, wav, mp3, flac, webm)
- **Output:** `Response` với `data` = danh sách chuỗi câu đã transcribe
- **Trường hợp lỗi:**
  - Định dạng sai hoặc lỗi decode — trả về `success: false`, `code: 400`
- **Dependencies:** `pydub` (Python) + `ffmpeg` (binary hệ thống)

#### 8.1.3 `start_audio_background_capture()`
Bắt đầu vòng lặp capture âm thanh nền (hotword + ASR).

- **Input:** Không
- **Output:** `None` (không có Response; bắt đầu luồng capture)
- **Luồng (threading):** Callback khi phát hiện hotword được chạy trong **daemon worker thread** để hotword loop vẫn phản hồi trong lúc phiên lệnh đang được transcribe.

#### 8.1.4 `stop_audio_background_capture()`
Dừng vòng lặp capture âm thanh nền.

- **Input:** Không
- **Output:** `None` (không có Response; dừng luồng capture)

### 8.2 Cấu hình Audio Capture

| Thông số | Biến môi trường | Mặc định | Mô tả |
|----------|----------------|----------|-------|
| Engine | `AUDIO_CAPTURE_ENGINE` | `vosk` | Engine ASR: `vosk` (offline) hoặc `deepgram` (cloud) |
| Device ID | `AUDIO_CAPTURE_DEVICE_ID` | `None` | ID thiết bị micro (mặc định hệ thống nếu không đặt) |
| Hotwords | `AUDIO_CAPTURE_HOTWORDS` | `hello` | Các hotword (phân tách dấu phẩy) để kích hoạt nghe |
| Patience | `AUDIO_CAPTURE_PATIENCE` | `3` | Số giây im lặng trước khi kết thúc phiên lệnh |
| ASR Model | `AUDIO_CAPTURE_MODEL_ID` | `vosk-model-small-en-us-0.15` | Tên model Vosk ASR (chỉ engine vosk) |
| Sample Rate | `AUDIO_CAPTURE_SAMPLE_RATE` | `16000` | Sample rate micro (Hz) |
| Channels | `AUDIO_CAPTURE_CHANNELS` | `1` | Số kênh micro |
| Silence Threshold | `AUDIO_CAPTURE_SILENCE_THRESHOLD` | `0.01` | Ngưỡng RMS im lặng, chuẩn hóa [-1,1] |
| Deepgram API Key | `DEEPGRAM_API_KEY` | `""` | API key Deepgram (chỉ engine deepgram) |
| Deepgram Model | `DEEPGRAM_MODEL` | `flux-general-en` | Tên model Deepgram (chỉ engine deepgram) |

### 8.3 Trạng thái dịch vụ

Nếu dependency cần thiết không có (`sounddevice`/`vosk` cho engine vosk, `sounddevice`/`deepgram` cho engine deepgram), hoặc micro lỗi, dịch vụ đăng ký là không khả dụng. `get_audio_tasks` trả về `code: 503`. Kiểm tra `GET /status` xem `audio_capture.available`.

---

## 9. Health Check — `/health`

Một endpoint HTTP GET đơn giản (không phải MCP tool).

- **Phương thức:** `GET`
- **Output:** `{"message": "OK"}`

---

## 10. Trạng thái dịch vụ (Service Status) — `/status`

Trả về tình trạng khả dụng của tất cả hardware service. Sử dụng endpoint này để kiểm tra service nào đang kết nối trước khi gọi API của chúng.

- **Phương thức:** `GET`
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

**Giá trị `available`:**
- `true` — service đã khởi động và kết nối thành công
- `false` — service kết nối thất bại (`error` chứa lý do)
- `null` — service chưa được khởi tạo (tạm thời, sẽ resolve sau khi startup)

**Khi một service không khả dụng**, gọi MCP tool của nó sẽ trả về `Response(success=false, code=503, message="... not available: <reason>")` thay vì crash.

---

## 11. Device Watcher — Tự động phục hồi

Device Watcher giám sát tất cả hardware service và tự động restart khi chúng bị lỗi (cáp USB bị ngắt, process crash, device timeout, hoặc robot chưa boot xong). Nó chạy một polling thread nền kiểm tra sức khỏe của từng service theo chu kỳ.

### 11.1 Hành vi

- **Kiểm tra sức khỏe:** Mỗi `DEVICE_WATCHER_POLL_INTERVAL` giây, watcher gọi `is_healthy()` trên từng service đã đăng ký
- **Phục hồi:** Khi phát hiện service không khỏe, watcher gọi `restart()` (stop + start) với exponential backoff
- **Backoff:** Bắt đầu từ `DEVICE_WATCHER_BASE_BACKOFF` giây, nhân đôi mỗi lần retry, giới hạn tối đa `DEVICE_WATCHER_MAX_BACKOFF`
- **Kết nối ban đầu vs phục hồi runtime:** Watcher theo dõi mỗi service đã **từng healthy chưa**. Service chưa bao giờ healthy (ví dụ robot chưa boot khi server khởi động) sẽ retry **không giới hạn** cho đến khi kết nối thành công. Service đã từng healthy nhưng sau đó lỗi sẽ tuân theo giới hạn `DEVICE_WATCHER_MAX_RETRIES`.
- **Thời gian chờ ban đầu:** Watcher chờ `DEVICE_WATCHER_INITIAL_GRACE_PERIOD` giây sau khi khởi động trước khi kiểm tra lần đầu, cho các service thời gian khởi tạo
- **Bỏ qua stub:** Các stub service (dùng khi chưa cài hardware dependencies) không được giám sát

### 11.2 Các service được giám sát

| Service | Kiểm tra sức khỏe | Hành động phục hồi |
|---------|-------------------|---------------------|
| sport | SDK client đã khởi tạo và sẵn sàng | Khởi tạo lại ChannelFactory, tạo lại SportClient, rebuild API mapping |
| depth_camera | Thread sống + pipeline hoạt động | Dừng pipeline, khởi tạo lại RealSense, restart thread |
| local_camera | Thread sống | Giải phóng VideoCapture, mở lại device, restart thread |
| rpc_camera | Thread sống | Khởi tạo lại Unitree VideoClient, restart thread |
| state_ros2 | Process sống + reader thread sống | Kill subprocess, drain queue, dọn semaphore, restart |
| audio_capture | Thread sống | Dừng device, restart capture thread |
| speaker | Audio stream đang hoạt động | Reset OutputStream (abort + tạo lại) |

### 11.3 Cấu hình

| Tham số | Biến môi trường | Mặc định | Mô tả |
|---------|----------------|----------|-------|
| Bật/Tắt | `DEVICE_WATCHER_ENABLED` | `true` | Bật/tắt device watcher |
| Chu kỳ kiểm tra | `DEVICE_WATCHER_POLL_INTERVAL` | `5.0` | Giây giữa các lần kiểm tra |
| Backoff cơ sở | `DEVICE_WATCHER_BASE_BACKOFF` | `2.0` | Delay retry cơ sở (giây) |
| Backoff tối đa | `DEVICE_WATCHER_MAX_BACKOFF` | `120.0` | Giới hạn delay retry tối đa (giây) |
| Số retry tối đa | `DEVICE_WATCHER_MAX_RETRIES` | `5` | Số lần restart tối đa cho lỗi runtime (0 = không giới hạn). Kết nối ban đầu luôn không giới hạn. |
| Thời gian chờ | `DEVICE_WATCHER_INITIAL_GRACE_PERIOD` | `10.0` | Chờ trước khi kiểm tra lần đầu |

### 11.4 Trạng thái

Endpoint `/status` bao gồm section `device_watcher` hiển thị trạng thái từng service:

```json
{
  "device_watcher": {
    "sport": { "state": "healthy", "retry_count": 0, "max_retries": 5, "ever_healthy": true },
    "rpc_camera": { "state": "recovering", "retry_count": 8, "max_retries": 5, "ever_healthy": false },
    "local_camera": { "state": "recovering", "retry_count": 2, "max_retries": 5, "ever_healthy": true }
  }
}
```

Các trạng thái: `healthy` (hoạt động bình thường), `recovering` (đang retry restart), `failed` (đã bỏ cuộc sau max retries — chỉ áp dụng cho service từng healthy trước đó).

Field `ever_healthy` cho biết service đã từng kết nối thành công chưa. Khi `false`, watcher retry không giới hạn (chế độ kết nối ban đầu).

---

## 12. DL Backend — Server Phát hiện Vật thể

FastAPI server độc lập (`dlbackend/`) cung cấp phát hiện vật thể zero-shot qua **YOLO-World** và **Grounding DINO**. Đóng vai trò backend phát hiện cho pipeline depth camera.

### 12.1 Các Endpoint

Tất cả endpoint nằm dưới prefix `/api/dl`.

#### 12.1.1 `POST /api/dl/yoloworld`

Chạy phát hiện zero-shot YOLO-World sử dụng ultralytics.

- **Input:** `DetectionRequest` (JSON)
  - `image_b64` (str, bắt buộc) — ảnh JPEG hoặc PNG mã hóa base64
  - `classes` (list[str], tùy chọn) — danh sách class vật thể cần phát hiện. Nếu bỏ qua, ~400 class mặc định được dùng.
- **Output:** Mảng JSON các `DetectionResult`:
```json
[
  { "class_name": "person", "xywh": [320.5, 240.0, 80.0, 160.0], "confidence": 0.92 }
]
```
- `xywh`: `[tâm_x, tâm_y, rộng, cao]` tính bằng pixel
- `confidence`: độ tin cậy phát hiện

#### 12.1.2 `POST /api/dl/grounding-dino`

Chạy phát hiện zero-shot Grounding DINO sử dụng HuggingFace transformers. Cùng format request/response với YOLO-World.

#### 12.1.3 `GET /api/dl/health`

Kiểm tra health, trả về trạng thái khả dụng của model.

```json
{
  "status": "ok",
  "yolo_world": true,
  "grounding_dino": true
}
```

### 12.2 Cấu hình

Model được cấu hình qua `dlbackend/.env`:

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `YOLO_WORLD_MODEL` | `yolov8x-worldv2.pt` | Phiên bản model YOLO-World |
| `GROUNDING_DINO_MODEL` | `IDEA-Research/grounding-dino-tiny` | ID model Grounding DINO trên HuggingFace |

### 12.3 Class mặc định

Khi `classes` bị bỏ qua trong request, ~400 class mặc định được sử dụng, bao gồm:

| Danh mục | Số lượng | Ví dụ |
|----------|----------|-------|
| Vật thể trong nhà | 100 | ghế, bàn, tủ lạnh, đèn, toilet |
| Vật thể ngoài trời | 100 | ô tô, đèn giao thông, trụ cứu hỏa, ghế dài, hàng rào |
| Vật thể tự nhiên | 100 | đại bàng, bướm, cây sồi, nấm, thác nước |
| Vật thể tổng quát | 100 | động vật, thức ăn, quần áo, dụng cụ, guitar, drone |

### 12.4 Triển khai

DL backend chạy trên server GPU riêng. Xem `dlbackend/README.md` để biết hướng dẫn cài đặt, triển khai Docker, và cấu hình RunPod/nginx.

Để tích hợp với GO2 middle layer, đặt `DEFAULT_REMOTE_DETECTOR_URL` trong `.env` chính:

```env
DEFAULT_REMOTE_DETECTOR_URL=https://<host>/api/dl/yoloworld
```
