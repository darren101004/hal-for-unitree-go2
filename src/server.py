import logging
import os
import sys
from contextlib import AsyncExitStack
from typing import Callable

from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from mcps.sport import start_sport_service
from mcps.sport import mcp as sport_mcp
from mcps.sportstate import start_state_background_reader, stop_state_background_reader
from mcps.sportstate import mcp as state_mcp
from dependencies import init_container
from starlette.middleware import Middleware
from starlette.middleware.exceptions import ExceptionMiddleware

from mcps.configs import setup_logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

setup_logging()
logger = logging.getLogger("Go2SportServer")

middleware = [Middleware(ExceptionMiddleware)]
sport_mcp_http = sport_mcp.http_app(
    path="/mcp",
    middleware=middleware,
    stateless_http=True,
)

state_mcp_http = state_mcp.http_app(
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
                "mcps.sport",
                "mcps.sportstate",
                "usecases",
                "interfaces",
                "impl",
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

        state_svc = _container.state_service_using_ros2()
        if hasattr(state_svc, "is_healthy") and not _is_stub(state_svc):
            watcher.register("state_ros2", state_svc.is_healthy, state_svc.restart)

        # Only watch services that have real implementations (not stubs).
        # Stubs have restart as a no-op and is_healthy always False.
        watchable = [
            ("sport", sport),
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
        logger.info("Initialize all singleton services at application startup.")
        async with AsyncExitStack() as stack:
            _start_service("sport", start_sport_service)
            _start_service("state_background_reader", start_state_background_reader)

            # Device watcher — must start after all services
            _start_device_watcher()

            for mcp in [
                sport_mcp_http,
                state_mcp_http,
            ]:
                logger.info(f"Entering lifespan for {mcp.__module__}")
                await stack.enter_async_context(mcp.lifespan(app))

            yield
    finally:
        logger.info("Graceful shutdown initiated. Cleaning up services...")
        # Stop watcher first so it doesn't try to restart dying services
        _stop_device_watcher()
        _stop_service("state_background_reader", stop_state_background_reader)
        logger.info("Graceful shutdown complete.")


app = FastAPI(name="go2-sport-control", lifespan=combined_lifespan)

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
