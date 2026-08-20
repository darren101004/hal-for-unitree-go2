"""
Device Watcher — monitors hardware services and auto-restarts on failure.

Runs a single background polling thread that checks the health of all
registered services.  When a service is detected as unhealthy (dead thread,
crashed process, disconnected device), the watcher attempts to restart it
with exponential backoff.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

import service_registry

logger = logging.getLogger("DeviceWatcher")


@dataclass
class WatchEntry:
    """Describes a watched service."""

    name: str
    is_healthy: Callable[[], bool]
    restart: Callable[[], None]
    max_retries: int = 5
    retry_count: int = field(default=0, init=False)
    last_failure_time: float = field(default=0.0, init=False)
    state: str = field(default="healthy", init=False)  # healthy | recovering | failed
    ever_healthy: bool = field(default=False, init=False)


class DeviceWatcherService:
    """Central service that monitors hardware services and auto-restarts them.

    Args:
        poll_interval: Seconds between health checks.
        base_backoff: Base backoff in seconds for retry delay.
        max_backoff: Maximum backoff cap in seconds.
        max_retries: Max restart attempts per service (0 = unlimited).
        initial_grace_period: Seconds to wait after start before first poll,
            giving services time to initialize.
    """

    def __init__(
        self,
        poll_interval: float = 5.0,
        base_backoff: float = 2.0,
        max_backoff: float = 120.0,
        max_retries: int = 5,
        initial_grace_period: float = 10.0,
    ) -> None:
        self._poll_interval = poll_interval
        self._base_backoff = base_backoff
        self._max_backoff = max_backoff
        self._default_max_retries = max_retries
        self._initial_grace_period = initial_grace_period

        self._entries: dict[str, WatchEntry] = {}
        self._entries_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ── Registration ──────────────────────────────────────────────

    def register(
        self,
        name: str,
        is_healthy: Callable[[], bool],
        restart: Callable[[], None],
        max_retries: int | None = None,
    ) -> None:
        """Register a service to be watched.

        Checks current health on registration to seed ``ever_healthy``.
        """
        entry = WatchEntry(
            name=name,
            is_healthy=is_healthy,
            restart=restart,
            max_retries=(
                max_retries if max_retries is not None else self._default_max_retries
            ),
        )
        try:
            entry.ever_healthy = is_healthy()
        except Exception:
            entry.ever_healthy = False
        with self._entries_lock:
            self._entries[name] = entry
        logger.info(
            "DeviceWatcher: Registered: %s (currently %s)",
            name,
            "healthy" if entry.ever_healthy else "not healthy",
        )

    def unregister(self, name: str) -> None:
        """Remove a service from the watch list."""
        with self._entries_lock:
            self._entries.pop(name, None)
        logger.info("DeviceWatcher: Unregistered: %s", name)

    # ── Health check / recovery ───────────────────────────────────

    def _get_backoff(self, entry: WatchEntry) -> float:
        """Exponential backoff: base * 2^(retry_count-1), capped at max_backoff."""
        if entry.retry_count <= 0:
            return 0.0
        return min(
            self._base_backoff * (2 ** (entry.retry_count - 1)),
            self._max_backoff,
        )

    def _check_and_recover(self, entry: WatchEntry) -> None:
        """Check one service and attempt recovery if unhealthy."""
        try:
            healthy = entry.is_healthy()
        except Exception as exc:
            logger.warning(
                "DeviceWatcher: Health check error for %s: %s", entry.name, exc
            )
            healthy = False

        # ── Healthy path ──
        if healthy:
            if entry.state != "healthy":
                logger.info(
                    "DeviceWatcher: %s recovered (was %s, after %d retries)",
                    entry.name,
                    entry.state,
                    entry.retry_count,
                )
                entry.state = "healthy"
                entry.retry_count = 0
                entry.last_failure_time = 0.0
                service_registry.register(entry.name, True)
            entry.ever_healthy = True
            return

        # ── Unhealthy path ──
        if entry.state == "healthy":
            logger.warning(
                "DeviceWatcher: %s is unhealthy, starting recovery", entry.name
            )
            entry.state = "recovering"
            entry.last_failure_time = time.time()
            service_registry.register(
                entry.name, False, "Device disconnected or service died"
            )

        if entry.state == "failed":
            return  # gave up

        # Check backoff
        backoff = self._get_backoff(entry)
        if time.time() - entry.last_failure_time < backoff:
            return  # still waiting

        # Check retries — skip limit for services that have never been healthy
        # (e.g. robot not booted yet when server started).
        if entry.ever_healthy and 0 < entry.max_retries <= entry.retry_count:
            logger.error(
                "DeviceWatcher: %s exceeded max retries (%d), giving up",
                entry.name,
                entry.max_retries,
            )
            entry.state = "failed"
            service_registry.register(
                entry.name,
                False,
                f"Exceeded max retries ({entry.max_retries})",
            )
            return

        # Attempt restart
        entry.retry_count += 1
        retries_label = (
            "unlimited (initial connect)"
            if not entry.ever_healthy
            else (str(entry.max_retries) if entry.max_retries > 0 else "unlimited")
        )
        logger.info(
            "DeviceWatcher: Restarting %s (attempt %d/%s, backoff %.1fs)",
            entry.name,
            entry.retry_count,
            retries_label,
            backoff,
        )
        try:
            entry.restart()
            entry.last_failure_time = time.time()
            logger.info("DeviceWatcher: Restart call completed for %s", entry.name)
        except Exception as exc:
            entry.last_failure_time = time.time()
            logger.error("DeviceWatcher: Restart failed for %s: %s", entry.name, exc)
            service_registry.register(entry.name, False, f"Restart failed: {exc}")

    # ── Poll loop ─────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        logger.info(
            "DeviceWatcher: Poll loop started (interval=%.1fs, grace=%.1fs)",
            self._poll_interval,
            self._initial_grace_period,
        )

        # Wait for services to finish their initial start() calls
        if not self._stop_event.wait(timeout=self._initial_grace_period):
            logger.info("DeviceWatcher: Grace period elapsed, beginning health checks")

        while not self._stop_event.is_set():
            with self._entries_lock:
                entries = list(self._entries.values())
            for entry in entries:
                if self._stop_event.is_set():
                    break
                self._check_and_recover(entry)
            self._stop_event.wait(timeout=self._poll_interval)

        logger.info("DeviceWatcher: Poll loop stopped")

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        """Start the watcher polling thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="device_watcher_thread",
        )
        self._thread.start()
        service_registry.register("device_watcher", True)
        logger.info("DeviceWatcher: Started")

    def stop(self) -> None:
        """Stop the watcher polling thread."""
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join(timeout=5.0)
        self._thread = None
        logger.info("DeviceWatcher: Stopped")

    # ── Status ────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Return current watch status for all registered services."""
        with self._entries_lock:
            return {
                name: {
                    "state": e.state,
                    "retry_count": e.retry_count,
                    "max_retries": e.max_retries,
                    "ever_healthy": e.ever_healthy,
                }
                for name, e in self._entries.items()
            }
