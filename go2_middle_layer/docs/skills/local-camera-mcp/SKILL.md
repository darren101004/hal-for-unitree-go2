---
name: go2-local-camera-mcp
description: Use the GO2 robot local camera MCP to capture images from the onboard USB/local webcam. Use when the user wants to see what the local camera sees, or when the robot's built-in RPC camera is unavailable.
---

# GO2 Local Camera MCP Skill

Use this skill when working with the GO2 middle layer local camera endpoint to capture images from a locally connected USB camera using OpenCV. The camera device is auto-detected on startup (scans indices 0–4) or can be set manually via environment variable. Background capture runs continuously.

## Endpoint

| Environment | URL |
|-------------|-----|
| Local | `http://localhost:8001/local_camera/mcp` |
| Robot network | `http://172.168.20.189:8001/local_camera/mcp` |

**MCP protocol:** HTTP POST with JSON-RPC. Client must accept `application/json` and `text/event-stream` in the `Accept` header.

## Tools

### `capture_image`

Capture the latest frame from the local USB camera.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `need_description` | `bool` | No | `false` | Accepted for API compatibility but **not supported** — local camera does not provide scene descriptions. Value is ignored. |

**Returns:** A `Response` object:

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether the capture succeeded |
| `message` | `str` | Human-readable status message |
| `data` | `str \| null` | Base64-encoded PNG image string on success |
| `code` | `int` | Status code (see below) |

**Response codes:**

| Code | Meaning |
|------|---------|
| `200` | Success — `data` contains the base64-encoded PNG image |
| `425` | Buffer not ready — background capture has not produced a frame yet. Retry after a short delay |
| `400` | Capture failed — camera returned an error or encoding failed |
| `503` | Camera unavailable — no USB camera found or device could not be opened |

## Usage Examples

| User intent | Tool call | Notes |
|-------------|-----------|-------|
| "Show me the webcam" | `capture_image()` | Returns latest frame from USB camera |
| "Take a photo from local cam" | `capture_image()` | Same tool |
| "Robot camera is down, use backup" | `capture_image()` | Fallback when RPC camera is unavailable |

## Configuration

| Parameter | Env var | Default | Description |
|-----------|---------|---------|-------------|
| Device ID | `LOCAL_CAMERA_DEVICE_ID` | Auto-detect (first available, scans 0–4) | OpenCV device index or path |
| Resolution | — | 1280 x 720 | Set via OpenCV properties |
| FPS | — | 30 | Capture loop interval |

## Prerequisites

- Requires a USB camera (webcam) connected to the machine.
- Uses OpenCV (`cv2`), which is included in the project dependencies.
- If no camera device is found, the service logs a warning and returns `code: 503`.

## Health Check

`GET http://localhost:8001/health` -> `{"message": "OK"}`

Check camera availability: `GET http://localhost:8001/status` -> look for `local_camera.available`.
