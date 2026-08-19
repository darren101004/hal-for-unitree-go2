# Phân tích mức sử dụng CPU

Phân tích các pattern tiêu tốn CPU trong codebase GO2 Middle Layer.

## Trạng thái

Tất cả vấn đề CPU ở tầng software đã được fix. Các mục còn lại phụ thuộc phần cứng, cần test trên robot thực mới xác định được giá trị tối ưu.

---

## Còn lại — Cần test trên phần cứng

### 1. Sport Controller vòng lặp 100Hz

**File:** `src/usecases/sport_controller.py` (dòng 36, 138)

Vòng lặp lệnh di chuyển chạy ở 100Hz (`loop_interval_sec = 0.01`). GO2 SDK thường xử lý lệnh ở 50Hz hoặc thấp hơn, nên có thể dư. Giảm xuống 20-50Hz tiết kiệm CPU nhưng có thể ảnh hưởng độ mượt hoặc thời gian phản hồi chướng ngại vật.

Giá trị đã configurable qua `_policy.loop_interval_sec`.

### 2. ROS2 Spin Loop — Timeout ngắn

**File:** `src/impl/state/sdk_state_service.py` (dòng 102-110)

`spin_once(timeout_sec=0.1)` gây 10 lần wakeup/giây khi idle. Tăng lên 0.5s giảm wakeup nhưng state update có thể trễ thêm 400ms.

### 3. YOLO Inference — Không cache

**File:** `src/impl/utils.py` (dòng 94-151)

Khi `need_description=True`, mỗi request depth camera kích hoạt YOLO detection + captioning. Cache kết quả với TTL ngắn tránh inference thừa, nhưng TTL tối ưu phụ thuộc tốc độ di chuyển robot.

---

## Tóm tắt

| Trạng thái | Thành phần | Ghi chú |
|------------|------------|---------|
| Cần test hardware | Sport controller | 100Hz, đã configurable, cần test tìm giá trị tối ưu |
| Cần test hardware | ROS2 spin timeout | 0.1s, tăng lên đổi latency lấy CPU |
| Cần test hardware | YOLO inference | Cache TTL phụ thuộc tốc độ robot |
