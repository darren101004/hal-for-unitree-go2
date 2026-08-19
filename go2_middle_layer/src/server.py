import logging
import os
import sys
from contextlib import AsyncExitStack
from typing import Callable

from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from mcps.rpc_camera import (
    start_rpc_camera_background_capture,
    stop_rpc_camera_background_capture,
)
from mcps.rpc_camera import mcp as rpc_camera_mcp
from mcps.depth_camera import (
    start_depth_camera_background_capture,
    stop_depth_camera_background_capture,
)
from mcps.depth_camera import mcp as depth_camera_mcp
from mcps.local_camera import (
    start_local_camera_background_capture,
    stop_local_camera_background_capture,
)
from mcps.local_camera import mcp as local_camera_mcp
from mcps.sport import start_sport_service
from mcps.sport import mcp as sport_mcp
from mcps.sportstate import start_state_background_reader, stop_state_background_reader
from mcps.sportstate import mcp as state_mcp
from mcps.speaker import start_speaker_service
from mcps.speaker import mcp as speaker_mcp
from mcps.audio_capture import (
    start_audio_background_capture,
    stop_audio_background_capture,
)
from mcps.audio_capture import mcp as audio_capture_mcp
from dependencies import init_container
from starlette.middleware import Middleware
from starlette.middleware.exceptions import ExceptionMiddleware

from mcps.configs import setup_logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

setup_logging()
logger = logging.getLogger("Go2MiddleLayerServer")

middleware = [Middleware(ExceptionMiddleware)]
sport_mcp_http = sport_mcp.http_app(
    path="/mcp",
    middleware=middleware,
    stateless_http=True,
)

rpc_camera_mcp_http = rpc_camera_mcp.http_app(
    path="/mcp",
    middleware=middleware,
    stateless_http=True,
)

depth_camera_mcp_http = depth_camera_mcp.http_app(
    path="/mcp",
    middleware=middleware,
    stateless_http=True,
)

local_camera_mcp_http = local_camera_mcp.http_app(
    path="/mcp",
    middleware=middleware,
    stateless_http=True,
)

state_mcp_http = state_mcp.http_app(
    path="/mcp",
    middleware=middleware,
    stateless_http=True,
)

speaker_mcp_http = speaker_mcp.http_app(
    path="/mcp",
    middleware=middleware,
    stateless_http=True,
)

audio_capture_mcp_http = audio_capture_mcp.http_app(
    path="/mcp",
    middleware=middleware,
    stateless_http=True,
)

# ------ Dependency injection setup ------
_container = None


def wire_container():
    global _container
    if _container is None:
        _container = init_container()
        # List all modules referencing Provide:
        _container.wire(
            modules=[
                __name__,
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
                "impl.device_watcher",
            ]
        )


# ---------------------------------------


def _stop_service(name: str, stop_fn: Callable[[], None]) -> None:
    """Stop a service, logging errors without blocking other cleanup."""
    try:
        logger.info("Stopping %s...", name)
        stop_fn()
        logger.info("%s stopped.", name)
    except Exception as e:
        logger.exception("Error stopping %s: %s", name, e)


def _start_service(name: str, start_fn: Callable[[], None]) -> None:
    """Start a service, logging errors without crashing the server."""
    try:
        logger.info("Starting %s...", name)
        start_fn()
        logger.info("%s started.", name)
    except Exception as e:
        logger.exception("Error starting %s: %s", name, e)


def _is_stub(service: object) -> bool:
    """Return True if the service is a stub (class name contains 'Stub')."""
    return "Stub" in type(service).__name__


_device_watcher = None


def _start_device_watcher() -> None:
    """Register all services with the device watcher and start it."""
    global _device_watcher

    if _container is None:
        return

    enabled = _container.config.device_watcher.enabled()
    if not enabled:
        logger.info("Device watcher disabled via config.")
        return

    try:
        watcher = _container.device_watcher_service()

        sport = _container.sport_service()
        depth_cam = _container.depth_camera_service()
        local_cam = _container.local_camera_service()
        rpc_cam = _container.rpc_camera_service()
        audio = _container.audio_capture_service()
        speaker = _container.speaker_service()

        state_svc = _container.state_service_using_ros2()
        if hasattr(state_svc, "is_healthy") and not _is_stub(state_svc):
            watcher.register("state_ros2", state_svc.is_healthy, state_svc.restart)

        # Only watch services that have real implementations (not stubs).
        # Stubs have restart as a no-op and is_healthy always False.
        watchable = [
            ("sport", sport),
            ("depth_camera", depth_cam),
            ("local_camera", local_cam),
            ("rpc_camera", rpc_cam),
            ("audio_capture", audio),
            ("speaker", speaker),
        ]
        for name, svc in watchable:
            if hasattr(svc, "is_healthy") and not _is_stub(svc):
                watcher.register(name, svc.is_healthy, svc.restart)

        _device_watcher = watcher
        _start_service("device_watcher", watcher.start)
    except Exception as e:
        logger.exception("Failed to start device watcher: %s", e)


def _stop_device_watcher() -> None:
    """Stop the device watcher if it is running."""
    global _device_watcher
    if _device_watcher is not None:
        _stop_service("device_watcher", _device_watcher.stop)
        _device_watcher = None


@asynccontextmanager
async def combined_lifespan(app: FastAPI):
    try:
        # Wire DI container at startup (for programmatic/uvicorn CLI cases)
        wire_container()
        rpc_fps = int(_container.config.rpc_camera.fps())
        depth_fps = int(_container.config.depth_camera.fps())
        logger.info("Initialize all singleton services at application startup.")
        async with AsyncExitStack() as stack:
            _start_service("sport", start_sport_service)
            _start_service("state_background_reader", start_state_background_reader)
            _start_service(
                "rpc_camera", lambda: start_rpc_camera_background_capture(fps=rpc_fps)
            )
            _start_service(
                "depth_camera",
                lambda: start_depth_camera_background_capture(fps=depth_fps),
            )
            _start_service(
                "local_camera", lambda: start_local_camera_background_capture(fps=30)
            )
            _start_service("audio_capture", start_audio_background_capture)
            _start_service("speaker", start_speaker_service)

            # Device watcher — must start after all services
            _start_device_watcher()

            for mcp in [
                sport_mcp_http,
                rpc_camera_mcp_http,
                depth_camera_mcp_http,
                local_camera_mcp_http,
                state_mcp_http,
                speaker_mcp_http,
                audio_capture_mcp_http,
            ]:
                logger.info(f"Entering lifespan for {mcp.__module__}")
                await stack.enter_async_context(mcp.lifespan(app))

            yield
    finally:
        logger.info("Graceful shutdown initiated. Cleaning up services...")
        # Stop watcher first so it doesn't try to restart dying services
        _stop_device_watcher()
        # Shutdown in reverse order (LIFO): audio -> local_camera -> depth_camera -> rpc_camera -> state
        _stop_service("audio_capture", stop_audio_background_capture)
        _stop_service("local_camera", stop_local_camera_background_capture)
        _stop_service("depth_camera", stop_depth_camera_background_capture)
        _stop_service("rpc_camera", stop_rpc_camera_background_capture)
        _stop_service("state_background_reader", stop_state_background_reader)
        logger.info("Graceful shutdown complete.")


app = FastAPI(name="go2-middle-layer", lifespan=combined_lifespan)

app.mount(
    "/sport_state",
    state_mcp_http,
    name="sport_state-legacy",
)

app.mount(
    "/sport",
    sport_mcp_http,
    name="sport-legacy",
)

app.mount(
    "/camera",
    rpc_camera_mcp_http,
    name="camera-legacy",
)

app.mount(
    "/depth_camera",
    depth_camera_mcp_http,
    name="depth_camera-legacy",
)

app.mount(
    "/local_camera",
    local_camera_mcp_http,
    name="local_camera-legacy",
)

app.mount(
    "/speaker",
    speaker_mcp_http,
    name="speaker-legacy",
)

app.mount(
    "/audio_capture",
    audio_capture_mcp_http,
    name="audio_capture-legacy",
)


@app.get("/health")
def health():
    return {"message": "OK"}


@app.get("/status")
def get_status():
    """Return availability status for all services. Use this to check which services are supported."""
    import service_registry

    services = service_registry.get_all()
    available_count = sum(1 for s in services.values() if s.get("available") is True)
    unavailable_count = sum(1 for s in services.values() if s.get("available") is False)
    unknown_count = sum(1 for s in services.values() if s.get("available") is None)
    result = {
        "status": (
            "healthy" if unavailable_count == 0 and unknown_count == 0 else "degraded"
        ),
        "summary": {
            "available": available_count,
            "unavailable": unavailable_count,
            "unknown": unknown_count,
        },
        "services": services,
    }

    if _device_watcher is not None:
        result["device_watcher"] = _device_watcher.get_status()

    return result


if __name__ == "__main__":
    import argparse
    import socket
    import uvicorn

    port = int(os.environ.get("PORT", 8001))
    shutdown_timeout = int(os.environ.get("UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN", 10))

    parser = argparse.ArgumentParser(description="Run MCP Server")
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=port,
        help="Port to run the server on (default: 8001)",
    )
    parser.add_argument(
        "--timeout-graceful-shutdown",
        type=int,
        default=shutdown_timeout,
        help="Seconds to wait for graceful shutdown (default: 10)",
    )
    parser.add_argument(
        "--no-port-fallback",
        action="store_true",
        help="Do not try next port if bind fails (default: try up to 10 ports)",
    )
    args = parser.parse_args()

    # Ensure DI is also wired if run via __main__
    wire_container()

    def _is_port_in_use(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("127.0.0.1", p)) == 0

    bind_port = args.port
    if not args.no_port_fallback:
        for attempt in range(10):
            try_port = args.port + attempt
            if not _is_port_in_use(try_port):
                bind_port = try_port
                break
            if attempt == 0:
                logger.warning(
                    "Port %s in use, trying next available port...", args.port
                )
            if attempt == 9:
                logger.error(
                    "No available port in range %s-%s. Use --no-port-fallback to disable.",
                    args.port,
                    args.port + 9,
                )
                raise SystemExit(1)
        if bind_port != args.port:
            logger.info("Using port %s (requested %s was in use)", bind_port, args.port)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=bind_port,
        log_level="debug",
        workers=1,
        timeout_graceful_shutdown=args.timeout_graceful_shutdown,
    )
