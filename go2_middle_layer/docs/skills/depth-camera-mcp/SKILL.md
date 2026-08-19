---
name: go2-depth-camera-mcp
description: Use the GO2 robot depth camera MCP for depth perception, object detection, and scene understanding. Use when the user wants to detect objects, measure distances, get 3D positions, or get a natural language scene description (Intel RealSense + YOLOv8).
---

# GO2 Depth Camera MCP Skill

Use this skill when working with the GO2 middle layer depth camera endpoint. Captures aligned color + depth frames from an Intel RealSense camera, runs YOLOv8 object detection (via remote inference server), estimates 3D world-coordinate positions for each detected object, and optionally generates a natural language scene description. Background capture runs continuously.

## Endpoint

| Environment | URL |
|-------------|-----|
| Local | `http://localhost:8001/depth_camera/mcp` |
| Robot network | `http://172.168.20.189:8001/depth_camera/mcp` |

**MCP protocol:** HTTP POST with JSON-RPC. Client must accept `application/json` and `text/event-stream` in the `Accept` header.

## Tools

### `capture_image`

Capture the latest frame from the depth camera with optional YOLO object detection and scene description.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `need_description` | `bool` | No | `false` | When `true`, runs YOLO detection + 3D position estimation and returns detected objects with distances, angles, and a natural language scene description. When `false`, returns only the color image (faster). |

**Returns:** A `Response` object:

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether the capture succeeded |
| `message` | `str` | Human-readable status message |
| `data` | `str \| null` | Base64-encoded JPEG image (color frame) |
| `code` | `int` | Status code (see below) |
| `extra_data` | `dict \| null` | Detection results when `need_description=true` (see below) |

**Response codes:**

| Code | Meaning |
|------|---------|
| `200` | Success — `data` contains the base64-encoded JPEG image |
| `425` | Buffer not ready — background capture has not produced a frame yet. Retry after a short delay |
| `400` | Capture failed — frame processing error |
| `503` | Camera unavailable — Intel RealSense not connected or `pyrealsense2` not installed |

**`extra_data` structure** (when `need_description=true`):

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
        "coordinates": [120.5, -50.3, 1480.0]
      }
    ],
    "natural_language_description": "At 2026-03-11 14:30:00:\nThe image is described as: ...\n1. person_1 at 150 centimeters, 15 degrees to the left of the center.\nNOTE: ..."
  }
}
```

**Object fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Object class with index suffix (e.g., `person_1`, `chair_2`) |
| `xyxyn` | `float[4]` | Normalized bounding box `[x_min, y_min, x_max, y_max]` (0.0–1.0) |
| `xyxy` | `int[4]` | Pixel bounding box `[x_min, y_min, x_max, y_max]` |
| `distance_to_object` | `int` | Distance from camera in millimeters |
| `coordinates` | `float[3]` | 3D position `[x, y, z]` in millimeters (camera coordinate frame) |

**Distance thresholds:**

| Range | Behavior |
|-------|----------|
| < 6000 mm | Object included in `objects` list with full 3D position |
| >= 6000 mm | Object listed in far range summary (names only, no position) |

## Usage Examples

| User intent | Tool call | Notes |
|-------------|-----------|-------|
| "What do you see?" | `capture_image(need_description=true)` | Full detection + description |
| "Take a quick photo" | `capture_image()` | Fast, image only, no detection |
| "How far is the person?" | `capture_image(need_description=true)` | Check `distance_to_object` in response |
| "Any obstacles ahead?" | `capture_image(need_description=true)` | Review detected objects and distances |

## Configuration

| Parameter | Env var | Default | Description |
|-----------|---------|---------|-------------|
| FPS | `DEPTH_CAMERA_FPS` | 30 | Background capture frame rate |
| Depth resolution | — | 1280 x 720 | Fixed |
| Color resolution | — | 1280 x 720 | Fixed |
| YOLO inference | `REMOTE_DETECTOR_URL` | (configured in `.env`) | Remote YOLOv8 detection server URL |

## Prerequisites

- Requires Intel RealSense camera and `pyrealsense2` Python package.
- YOLO detection requires a running remote detector server (configured via `REMOTE_DETECTOR_URL`).
- If hardware is unavailable, the service runs as a stub and returns `code: 503`.

## Health Check

`GET http://localhost:8001/health` -> `{"message": "OK"}`

Check camera availability: `GET http://localhost:8001/status` -> look for `depth_camera.available`.
