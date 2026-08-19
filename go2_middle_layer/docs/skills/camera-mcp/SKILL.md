---
name: go2-camera-mcp
description: Use the GO2 robot RPC camera MCP to capture images from the robot's built-in front camera. Use when the user wants to see what the robot sees, inspect surroundings, or verify the robot's position.
---

# GO2 RPC Camera MCP Skill

Use this skill when working with the GO2 middle layer camera endpoint to capture images from the robot's built-in front camera via Unitree SDK2 `VideoClient`. A background thread continuously captures frames at configurable FPS, and the MCP tool reads instantly from the latest buffer.

## Endpoint

| Environment | URL |
|-------------|-----|
| Local | `http://localhost:8001/camera/mcp` |
| Robot network | `http://172.168.20.189:8001/camera/mcp` |

**MCP protocol:** HTTP POST with JSON-RPC. Client must accept `application/json` and `text/event-stream` in the `Accept` header.

## Tools

### `capture_image`

Capture the latest frame from the robot's built-in RPC camera (first-person forward-facing view).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| *(none)* | — | — | No parameters needed |

**Returns:** A `Response` object with the following fields:

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
| `400` | Capture failed — the camera returned an error frame |
| `503` | Camera unavailable — hardware not connected or SDK not installed |

## Usage Examples

| User intent | Tool call | Notes |
|-------------|-----------|-------|
| "What do you see?" | `capture_image()` | Returns the robot's forward-facing view |
| "Take a picture" | `capture_image()` | Same tool, returns latest buffered frame |
| "Check surroundings" | `capture_image()` | Combine with depth camera for richer context |

## Configuration

| Parameter | Env var | Default | Description |
|-----------|---------|---------|-------------|
| FPS | `CAMERA_FPS` | 30 | Background capture frame rate |
| Resolution | — | 1280 x 720 | Fixed in SDK |

## Prerequisites

- Requires `unitree_sdk2py` to be installed. If unavailable, the service runs as a stub and returns `code: 503`.
- The server must be running (`make run`) and background capture starts automatically on server startup.

## Health Check

`GET http://localhost:8001/health` -> `{"message": "OK"}`

Check camera availability: `GET http://localhost:8001/status` -> look for `rpc_camera.available`.
