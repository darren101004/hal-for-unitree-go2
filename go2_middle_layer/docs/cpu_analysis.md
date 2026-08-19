# CPU Usage Analysis

Analysis of CPU-intensive patterns in the GO2 Middle Layer codebase.

## Status

All software-level CPU issues have been fixed. The remaining items are hardware-dependent tuning that cannot be verified without testing on the robot.

---

## Remaining — Requires hardware testing

### 1. Sport Controller 100Hz Loop

**File:** `src/usecases/sport_controller.py` (line 36, 138)

The movement command loop runs at 100Hz (`loop_interval_sec = 0.01`). The GO2 SDK typically processes commands at 50Hz or less, so this may be overkill. Reducing to 20-50Hz would save CPU but could affect motion smoothness or obstacle reaction time.

The value is already configurable via `_policy.loop_interval_sec`.

### 2. ROS2 Spin Loop — Short Timeout

**File:** `src/impl/state/sdk_state_service.py` (lines 102-110)

`spin_once(timeout_sec=0.1)` causes 10 wakeups/second even when idle. Increasing to 0.5s would reduce wakeups but add up to 400ms latency to state updates.

### 3. YOLO Inference — No Caching

**File:** `src/impl/utils.py` (lines 94-151)

When `need_description=True`, each depth camera request triggers YOLO detection + captioning. Caching results with a short TTL could avoid redundant inference, but the ideal TTL depends on robot movement speed.

---

## Summary

| Status | Component | Notes |
|--------|-----------|-------|
| Needs hardware test | Sport controller | 100Hz, configurable, test to find optimal value |
| Needs hardware test | ROS2 spin timeout | 0.1s, increase trades latency for CPU |
| Needs hardware test | YOLO inference | Cache TTL depends on robot speed |
