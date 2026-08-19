"""
Base primitives for audio capture (devices + services).

This module defines:
- `resolve_input_device_id`       — helper to choose a microphone device
- `BaseAudioCaptureDevice`       — abstract mic + hotword device
- `BaseAudioCaptureService`      — abstract background service + task queue
"""

from __future__ import annotations

import logging
import queue
import threading
from abc import ABC, abstractmethod
from typing import Callable

import sounddevice as sd

import service_registry
from interfaces.audio import AudioCaptureService

logger = logging.getLogger("AudioCapture:BaseAudioCaptureDevice")


def resolve_input_device_id(device_id: int | str | None) -> tuple[int, str]:
    """
    Resolve an input audio (microphone) device ID with flexible logic:

    - None → auto-pick best microphone (prefer non-virtual, input-only devices)
    - int / str(int) → use as index
    - str → search by name substring (case-insensitive)
    - fallback → auto-pick

    Returns:
        (device_id, device_name)

    Raises:
        RuntimeError: If no input devices are found.
    """

    VIRTUAL_DEVICE_NAMES = {"pipewire", "pulse", "default", "dmix", "surround"}

    devices = sd.query_devices()
    logger.info(f"All Input Devices: {devices}")

    all_input_ids = []
    hardware_ids = []

    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            all_input_ids.append(i)

            name_lower = d["name"].strip().lower()
            virtual = any(v in name_lower for v in VIRTUAL_DEVICE_NAMES)
            has_output = d["max_output_channels"] > 0

            if not virtual and not has_output:
                hardware_ids.append(i)

    if not all_input_ids:
        raise RuntimeError("No input audio devices (microphones) found on this system.")

    def _auto_pick() -> tuple[int, str]:
        candidates = hardware_ids if hardware_ids else all_input_ids

        if len(hardware_ids) == 1:
            chosen = hardware_ids[0]
            logger.info(
                "Auto-selected hardware microphone [%d]: %s",
                chosen,
                devices[chosen]["name"],
            )
            return chosen, devices[chosen]["name"]

        chosen = candidates[0]
        logger.info(
            "Auto-selected input device: [%d] %s (in=%d, out=%d, sr=%d)",
            chosen,
            devices[chosen]["name"],
            devices[chosen]["max_input_channels"],
            devices[chosen]["max_output_channels"],
            devices[chosen]["default_samplerate"],
        )
        return chosen, devices[chosen]["name"]

    # 1. None → auto
    if device_id is None:
        logger.info("No input device_id specified, auto-picking.")
        return _auto_pick()

    # 2. int or str of int
    int_candidate = None
    if isinstance(device_id, int) or (
        isinstance(device_id, str) and device_id.strip().isdigit()
    ):
        int_candidate = int(device_id)
    elif isinstance(device_id, str):
        try:
            int_candidate = int(device_id)
        except Exception:
            int_candidate = None

    if int_candidate is not None:
        try:
            info = sd.query_devices(int_candidate, "input")
            logger.info(f"Selected Input Device (with kind 'input'): {info}")

            if info.get("max_input_channels", 0) <= 0:
                raise ValueError("Device has no input channels")

            logger.info(
                "Selected input device by index [%d]: %s",
                int_candidate,
                info["name"],
            )
            return int_candidate, info["name"]

        except Exception as e:
            logger.warning(
                "Input device_id=%s invalid (%s). Falling back.",
                device_id,
                e,
            )
            return _auto_pick()

    # 3. Raw string search → search by name substring (case-insensitive)
    if isinstance(device_id, str):
        keyword = device_id.strip().lower()

        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0 and keyword in d["name"].lower():
                logger.info(
                    "Selected input device by name: [%d] %s",
                    i,
                    d["name"],
                )
                return i, d["name"]

        logger.warning(
            "No input device contains '%s'. Falling back to auto-pick.",
            device_id,
        )
        return _auto_pick()

    # Fallback → auto-pick
    logger.warning("Invalid input device_id=%s. Falling back.", device_id)
    return _auto_pick()


class BaseAudioCaptureDevice(ABC):
    """
    Abstract microphone device that supports hotword detection and command capture.

    Implementations must:
    - Call registered callbacks when a hotword is detected
    - Provide `listen()` to capture a command after a hotword
    """

    def __init__(
        self,
        device_id: int | None,
        sample_rate: int,
        channels: int,
        name: str,
    ) -> None:
        self.device_id = device_id
        self.sample_rate = sample_rate
        self.channels = channels
        self.name = name

        self.running = False
        self.callbacks: list[Callable[[str], None]] = []

        # Mode flag to avoid spawning overlapping "listen task" sessions.
        # When True: ignore further hotword triggers until the current
        # `listen(patience)` finishes and produces a task (if any).
        self._mode_lock = threading.Lock()
        self._listening_for_task = False

        self._queues: list[queue.Queue[bytes]] = []
        self._queues_lock = threading.Lock()

    def _try_enter_task_mode(self) -> bool:
        """Try switch from hotword mode -> task listen mode."""
        with self._mode_lock:
            if self._listening_for_task:
                return False
            self._listening_for_task = True
            return True

    def _exit_task_mode(self) -> None:
        """Exit task listen mode back to hotword mode."""
        with self._mode_lock:
            self._listening_for_task = False

    def register_queue(self, queue_: queue.Queue[bytes]) -> None:
        """Register a queue to receive raw microphone bytes."""
        with self._queues_lock:
            self._queues.append(queue_)

    def unregister_queue(self, queue_: queue.Queue[bytes]) -> None:
        """Unregister a previously registered microphone queue."""
        with self._queues_lock:
            if queue_ in self._queues:
                self._queues.remove(queue_)

    def _broadcast(self, indata) -> None:
        """Forward raw microphone bytes to all registered queues."""
        data = bytes(indata)
        with self._queues_lock:
            snapshot = list(self._queues)
        for q in snapshot:
            # Never block the audio callback thread:
            # if the queue is full, drop the frame.
            try:
                q.put_nowait(data)
            except queue.Full:
                continue

    @abstractmethod
    def start(self) -> None:
        """Start the hotword detection loop (blocking)."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """Signal the hotword detection loop to exit."""
        raise NotImplementedError

    @abstractmethod
    def listen(self, patience: int) -> str:
        """
        Listen for a command after a hotword.

        Args:
            patience: Seconds of silence before ending the capture session.

        Returns:
            Transcribed command string or empty string.
        """
        raise NotImplementedError


class BaseAudioCaptureService(AudioCaptureService, ABC):
    """
    Shared background-loop behavior for audio capture services.
    """

    def __init__(
        self,
        device_id: int | str | None = None,
        hotwords: list[str] | None = None,
        patience: int = 3,
        sample_rate: int = 16000,
        channels: int = 1,
        name: str | None = None,
    ) -> None:
        logger.info(f"Resolving device ID received: {device_id}")
        resolved_device_id, resolved_name = resolve_input_device_id(device_id)
        logger.info(f"Resolved device ID: {resolved_device_id}, {resolved_name}")

        self._device_id: int | None = resolved_device_id
        self._hotwords = hotwords or []
        self._patience = patience
        self._sample_rate = sample_rate
        self._channels = channels
        self._name = name

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._device: BaseAudioCaptureDevice | None = None

        self._tasks: list[str] = []
        self._tasks_lock = threading.Lock()

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Engine name for logging/status (e.g. 'vosk', 'deepgram')."""
        raise NotImplementedError

    @abstractmethod
    def _create_device(self) -> BaseAudioCaptureDevice:
        """Create the underlying device implementation."""
        raise NotImplementedError

    def _capture_loop(self) -> None:
        retry_delay = 2.0
        max_delay = 30.0

        while not self._stop_event.is_set():
            logger.info(
                "[AudioCapture:%s] Initialising device %s (hotwords=%s, patience=%ss)",
                self.engine_name,
                self._device_id,
                self._hotwords,
                self._patience,
            )
            try:
                self._device = self._create_device()
                service_registry.register(
                    "audio_capture",
                    True,
                    extra_data={
                        "engine": self.engine_name,
                        "device_id": self._device.device_id,
                        "device_name": self._device.name,
                        "sample_rate": self._device.sample_rate,
                        "channels": self._device.channels,
                        "hotwords": list(self._hotwords),
                    },
                )
            except Exception as exc:
                logger.error(
                    "[AudioCapture:%s] Failed to initialize device: %s",
                    self.engine_name,
                    exc,
                    exc_info=True,
                )
                service_registry.register("audio_capture", False, str(exc))
                if self._stop_event.is_set():
                    break
                logger.info(
                    "[AudioCapture:%s] Retrying device init in %.1fs...",
                    self.engine_name,
                    retry_delay,
                )
                self._stop_event.wait(retry_delay)
                retry_delay = min(retry_delay * 2, max_delay)
                continue

            retry_delay = 2.0

            def on_hotword(trigger_text: str) -> None:
                logger.info(
                    "[AudioCapture:%s] Hotword '%s' — listening for command...",
                    self.engine_name,
                    trigger_text,
                )
                task = self._device.listen(patience=self._patience)  # type: ignore[union-attr]
                if task:
                    logger.info(
                        "[AudioCapture:%s] Task enqueued: '%s'", self.engine_name, task
                    )
                    with self._tasks_lock:
                        self._tasks.append(task)
                else:
                    logger.info(
                        "[AudioCapture:%s] No command after hotword, discarded.",
                        self.engine_name,
                    )

            self._device.callbacks.append(on_hotword)

            try:
                self._device.start()  # blocks until device.running = False
            except Exception as exc:
                logger.error(
                    "[AudioCapture:%s] Capture loop error: %s",
                    self.engine_name,
                    exc,
                    exc_info=True,
                )
                service_registry.register("audio_capture", False, str(exc))

            logger.info("[AudioCapture:%s] Capture loop iteration exited.", self.engine_name)

            if self._stop_event.is_set():
                break

            logger.info(
                "[AudioCapture:%s] Restarting in %.1fs...",
                self.engine_name,
                retry_delay,
            )
            self._stop_event.wait(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)

        logger.info("[AudioCapture:%s] Capture loop stopped.", self.engine_name)

    def start(self) -> None:
        """Start the background capture thread (idempotent)."""
        if self._thread is not None and self._thread.is_alive():
            logger.debug(
                "[AudioCapture:%s] Background thread already running.", self.engine_name
            )
            return

        logger.info(
            "[AudioCapture:%s] Starting background capture thread.", self.engine_name
        )
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name=f"audio_capture_{self.engine_name}_thread",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the background capture thread."""
        if self._thread is None:
            return

        logger.info(
            "[AudioCapture:%s] Stopping background capture thread.", self.engine_name
        )
        self._stop_event.set()
        if self._device is not None:
            self._device.stop()

        self._thread.join(timeout=5.0)
        self._thread = None
        self._device = None

    def get_pending_tasks(self) -> list[str]:
        """Drain and return all accumulated voice tasks."""
        with self._tasks_lock:
            tasks = list(self._tasks)
            self._tasks.clear()
        return tasks

    def check_hotwords(self, text: str) -> bool:
        """Check if transcribed text contains any configured hotword."""
        import re

        if not self._hotwords or not text:
            return False
        normalized = re.sub(r"[^\w\s]", "", text.lower()).strip()
        return any(hw.lower() in normalized for hw in self._hotwords)
