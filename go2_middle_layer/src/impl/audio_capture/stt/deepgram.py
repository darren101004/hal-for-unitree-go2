"""
Deepgram audio capture implementation (device + service).
"""

from __future__ import annotations

import asyncio
import io
import logging
import queue
import threading
import time
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import noisereduce as nr
import numpy as np
import sounddevice as sd
from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from websockets.exceptions import ConnectionClosedError

from impl.audio_capture.base import (
    BaseAudioCaptureDevice,
    BaseAudioCaptureService,
    resolve_input_device_id,
)

logger = logging.getLogger("AudioCapture:DeepgramAudioCapture")


DEFAULT_HOTWORDS: list[str] = ["hey doggy", "hey doggi"]                  # default hotwords
KEYTERMS: list[str] = ["doggy", "doggi"]                                  # important terms for ASR engine (Deepgram)
DEFAULT_DEEPGRAM_MODEL= "flux-general-en"                                 # default Deepgram model for STT
DEFAULT_TRANSCRIPTION_MODEL = "nova-3"                                    # transcription model for performance/accuracy
DEFAULT_SAMPLE_RATE = 16000                                               # standard audio sample rate (Hz)
DEFAULT_CHANNELS = 1                                                      # number of input audio channels (1 = mono)
DEFAULT_PATIENCE_SECONDS = 3                                              # duration (s) to wait for user stop speaking
DEFAULT_MAX_TASK_DURATION_SECONDS: float = 60.0                           # maximum allowed task duration (s)
DEFAULT_SILENCE_RMS_THRESHOLD = 0.01                                      # RMS threshold considered as silence
DEFAULT_SILENCE_STE_RATIO: float = 0.5                                    # STE ratio for detecting silence or speech
DEFAULT_ACTIVE_DISCONNECT_AFTER_SEC: float = 60.0                         # seconds of activity before disconnect (WS refresh)
DEFAULT_PREROLL_SECONDS: float = 0.4                                      # duration (s) to prepend to utterance (pre-hotword context)
DEFAULT_TASK_SEPARATOR_SILENCE_SECONDS: float = 1.0                       # silence (s) separating logical tasks
TRANSCRIBE_TIMEOUT: float = 30.0                                          # timeout (s) for transcription operation
WS_SEND_TIMEOUT: float = 0.5                                              # timeout (s) to send audio to ASR backend via websocket
HOTWORD_CALLBACK_TIMEOUT: float = 30.0                                    # wait time (s) for hotword callback
TASK_MODE_EXIT_TIMEOUT: float = 35.0                                      # in "task mode", exit if no more speech after this (s)
MIC_STALL_WARN_AFTER_SEC: float = 2.0                                     # warn mic stall after (s)
MIC_STALL_WARN_REPEAT_SEC: float = 10.0                                   # repeat mic stall warning every (s) if still stalled
MIC_PRODUCER_RECENT_SEC: float = 0.6                                      # recent time range to check mic is still producing audio
MIC_RECONNECT_AFTER_SEC: float = 15.0                                     # duration (s) to retry reconnect when mic input lost
# Flux v2 EOT (WebSocket query; sent as strings — see Deepgram Listen Flux docs)
EOT_TIMEOUT_MS: str = "1000"
EOT_THRESHOLD: str = "0.8"
LISTEN_MAX_RETRIES: int = 3                                               # maximum number of listen loop retries
LISTEN_RETRY_BASE_DELAY: float = 1.0                                      # base delay (s) for exponential backoff on listen retry



class SilenceModeDisconnect(RuntimeError):
    """Raised to force websocket reconnect after prolonged silence mode."""


class MicStallDisconnect(RuntimeError):
    """Raised to force hotword loop reconnect after prolonged mic stall."""


def _flux_event_str(message: Any) -> str:
    ev = getattr(message, "event", None)
    if ev is None:
        return ""
    return str(getattr(ev, "value", ev))


def _is_end_of_turn_event(ev: str) -> bool:
    if not ev:
        return False
    n = ev.strip().lower().replace("_", "")
    return n in ("endofturn", "eot")


def _flux_turn_index(message: Any) -> int:
    raw = getattr(message, "turn_index", None)
    if raw is None:
        return 0
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return 0


@dataclass
class FluxListenTaskAccumulator:
    """
    Task listen mode for Flux: one sentence is committed only on EndOfTurn with
    non-empty transcript. Task finalization uses turn_index: after at least one
    such EOT, if a newer turn only receives empty transcripts, finalize after
    post_eot_empty_silence_sec (typically the configured patience seconds).
    """

    post_eot_empty_silence_sec: float = float(DEFAULT_PATIENCE_SECONDS)
    sentences: list[str] = field(default_factory=list)
    last_turn_with_nonempty_eot: int = -1
    _empty_new_turn_since: float | None = field(default=None, repr=False)

    def reset(self) -> None:
        self.sentences.clear()
        self.last_turn_with_nonempty_eot = -1
        self._empty_new_turn_since = None

    def handle_message(self, message: Any) -> None:
        try:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Deepgram MESSAGE: %r", message)
            ev = _flux_event_str(message)
            ti = _flux_turn_index(message)
            tx = (getattr(message, "transcript", "") or "").strip()

            if _is_end_of_turn_event(ev) and tx:
                self.sentences.append(tx)
                self.last_turn_with_nonempty_eot = ti
                logger.info("Turn EOT sentence: '%s' (turn_index=%s)", tx, ti)

            if self.last_turn_with_nonempty_eot < 0:
                return

            if ti > self.last_turn_with_nonempty_eot:
                if not tx:
                    if self._empty_new_turn_since is None:
                        self._empty_new_turn_since = time.time()
                        logger.info(
                            "New turn %s empty transcript — start %.1fs finalize window",
                            ti,
                            self.post_eot_empty_silence_sec,
                        )
                else:
                    if self._empty_new_turn_since is not None:
                        logger.info(
                            "New turn %s got text — clear post-EOT empty timer", ti
                        )
                    self._empty_new_turn_since = None
        except Exception as exc:
            logger.warning("FluxListenTaskAccumulator.handle_message error: %s", exc)

    def should_finalize_task(self) -> bool:
        if self._empty_new_turn_since is None:
            return False
        if self.last_turn_with_nonempty_eot < 0:
            return False
        return (
            time.time() - self._empty_new_turn_since
        ) >= self.post_eot_empty_silence_sec

    def finalize(self) -> str:
        return " ".join(self.sentences).strip()


class DeepgramFluxAudioCaptureDevice(BaseAudioCaptureDevice):
    """
    Microphone device using Deepgram Flux (v2) for hotword detection and ASR.
    """

    def __init__(
        self,
        device_id: int | None,
        api_key: str,
        model: str = DEFAULT_DEEPGRAM_MODEL,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        name: str | None = None,
        hotwords: list[str] | None = None,
        silence_rms_threshold: float = DEFAULT_SILENCE_RMS_THRESHOLD,
        blocksize: int = 2560,
        client_denoise: bool = False,
        max_task_duration: float = DEFAULT_MAX_TASK_DURATION_SECONDS,
    ) -> None:
        resolved_id, resolved_name = resolve_input_device_id(device_id)
        super().__init__(
            device_id=resolved_id,
            sample_rate=sample_rate,
            channels=channels,
            name=name or resolved_name,
        )

        self.api_key = api_key
        self.model = model
        self.max_task_duration = max_task_duration
        if hotwords is not None:
            hotwords = [re.sub(r"[^\w\s]", "", hw.lower()).strip() for hw in hotwords]
            self.hotwords = hotwords
        else:
            self.hotwords = list(DEFAULT_HOTWORDS)
        self.silence_rms_threshold = silence_rms_threshold
        self.blocksize = blocksize
        self._client_denoise = client_denoise
        self._client = AsyncDeepgramClient(api_key=api_key)

        logger.info("Initialized")
        logger.info("  model      : %s", self.model)
        logger.info("  hotwords   : %s", self.hotwords)
        logger.info("  sample_rate: %s", self.sample_rate)
        logger.info("  channels   : %s", self.channels)
        logger.info("  device_id  : %s", self.device_id)
        logger.info("  device_name: %s", self.name)

    def _denoise(self, data: bytes) -> bytes:
        if not self._client_denoise:
            return data
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        reduced = nr.reduce_noise(y=samples, sr=self.sample_rate)
        return (np.clip(reduced, -1.0, 1.0) * 32768.0).astype(np.int16).tobytes()

    async def _denoise_async(self, data: bytes) -> bytes:
        if not self._client_denoise:
            return data
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._denoise, data)

    def check_vad_by_using_ste(
        self,
        data: bytes,
        *,
        silence_rms_threshold: float | None = None,
    ) -> bool:
        """Short-Time Energy (STE) gate. Returns True if frame is likely speech."""
        if not data:
            return False
        samples = np.frombuffer(data, dtype=np.int16)
        if samples.size == 0:
            return False

        threshold_rms = silence_rms_threshold if silence_rms_threshold is not None else self.silence_rms_threshold
        threshold_scaled = threshold_rms * 32768.0
        rhs = samples.size * (threshold_scaled * threshold_scaled)
        s = samples.astype(np.int64)
        return float(np.sum(s * s)) > rhs

    def is_hotword(self, transcript: str) -> bool:
        transcript = re.sub(r"[^\w\s]", "", transcript.lower()).strip()
        return any(hw in transcript for hw in self.hotwords)

    def _build_hotword_options(self) -> dict:
        return {
            "model": self.model,
            "encoding": "linear16",
            "sample_rate": str(self.sample_rate),
            "keyterm": KEYTERMS,
            "eot_timeout_ms": EOT_TIMEOUT_MS,
            "eot_threshold": EOT_THRESHOLD,
        }

    def _build_task_options(self) -> dict:
        return {
            "model": self.model,
            "encoding": "linear16",
            "sample_rate": str(self.sample_rate),
            "eot_timeout_ms": EOT_TIMEOUT_MS,
            "eot_threshold": EOT_THRESHOLD,
        }

    def _is_in_task_mode(self) -> bool:
        with self._mode_lock:
            return self._listening_for_task

    async def _send_with_timeout(self, connection, data: bytes, context: str) -> None:
        try:
            await asyncio.wait_for(connection._send(data), timeout=WS_SEND_TIMEOUT)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(
                f"Deepgram send timeout during {context} after {WS_SEND_TIMEOUT:.1f}s"
            ) from exc
        except ConnectionClosedError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Deepgram send failed during {context}: {exc}") from exc

    async def _ws_sender(
        self,
        connection,
        send_queue: asyncio.Queue[bytes | None],
        *,
        strict: bool = False,
    ) -> None:
        """Drain send_queue and push to WS. Exits on None sentinel."""
        while True:
            data = await send_queue.get()
            if data is None:
                return
            try:
                await self._send_with_timeout(connection, data, "hotword stream")
            except (TimeoutError, ConnectionClosedError, RuntimeError) as exc:
                if strict:
                    raise RuntimeError(f"ws_sender fatal error: {exc}") from exc
                logger.warning("ws_sender error: %s — dropping frame", exc)

    def _make_mic_queue_and_callback(
        self, loop: asyncio.AbstractEventLoop
    ) -> tuple[asyncio.Queue[bytes], dict[str, float | int], object]:
        """Create a mic->queue callback pair for the hotword websocket loop."""
        mic_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=500)
        mic_diag: dict[str, float | int] = {
            "last_portaudio_cb_mono": time.monotonic(),
            "portaudio_cb_count": 0,
            "last_mic_queue_full_log_at": 0.0,
        }

        def enqueue_mic_raw(raw: bytes) -> None:
            try:
                mic_queue.put_nowait(raw)
            except asyncio.QueueFull:
                now_mono = time.monotonic()
                if now_mono - float(mic_diag["last_mic_queue_full_log_at"]) >= 1.0:
                    mic_diag["last_mic_queue_full_log_at"] = now_mono
                    logger.warning("mic_queue full — dropping raw frame")

        def sd_callback(indata, frames, t, s):
            if s:
                logger.warning("PortAudio stream status flags: %s", s)
            mic_diag["last_portaudio_cb_mono"] = time.monotonic()
            mic_diag["portaudio_cb_count"] += 1
            raw = bytes(indata)
            try:
                self._broadcast(indata)
            except Exception as exc:
                logger.warning("_broadcast error in sd_callback: %s", exc)
            try:
                loop.call_soon_threadsafe(enqueue_mic_raw, raw)
            except Exception as exc:
                logger.warning("mic_queue put error in sd_callback: %s", exc)

        return mic_queue, mic_diag, sd_callback

    def _attach_hotword_ws_handlers(
        self,
        connection,
        stream_state: dict[str, float],
    ) -> None:
        """Attach Deepgram hotword websocket handlers."""

        def on_message(message) -> None:
            try:
                transcript = (getattr(message, "transcript", "") or "").strip().lower()
                if not transcript:
                    return
                stream_state["last_deepgram_speech_at"] = time.time()
                logger.info("Heard: '%s'", transcript)
                if self._is_in_task_mode():
                    return
                if self.is_hotword(transcript):
                    logger.info("=====>Detected hotword: '%s'", transcript)
                    if not self._try_enter_task_mode():
                        return
                    logger.info(
                        "Hotword detected: '%s'. Running callbacks to capture task...",
                        transcript,
                    )

                    def run_callbacks() -> None:
                        task_mode_deadline = time.time() + TASK_MODE_EXIT_TIMEOUT
                        try:
                            for cb in list(self.callbacks):
                                callback_error: Exception | None = None

                                def callback_runner() -> None:
                                    nonlocal callback_error
                                    try:
                                        cb(transcript)
                                    except Exception as exc:
                                        callback_error = exc

                                callback_thread = threading.Thread(
                                    target=callback_runner,
                                    daemon=True,
                                )
                                callback_thread.start()

                                remaining = max(0.0, task_mode_deadline - time.time())
                                callback_thread.join(min(HOTWORD_CALLBACK_TIMEOUT, remaining))

                                if callback_thread.is_alive():
                                    logger.error(
                                        "hotword callback timeout after %.1fs; "
                                        "forcing task mode exit.",
                                        HOTWORD_CALLBACK_TIMEOUT,
                                    )
                                    return
                                if callback_error:
                                    logger.warning(
                                        "hotword callback error: %s",
                                        callback_error,
                                    )
                        except Exception as exc:
                            logger.warning("hotword callback error: %s", exc)
                        finally:
                            self._exit_task_mode()
                            stream_state["last_deepgram_speech_at"] = time.time()
                            logger.info(
                                "[active/hotword] Task mode exited — reset silence timer. Last speech at: %s",
                                stream_state["last_deepgram_speech_at"],
                            )

                    threading.Thread(target=run_callbacks, daemon=True).start()
            except Exception as exc:
                logger.warning("on_message error: %s", exc)

        connection.on(EventType.MESSAGE, on_message)
        connection.on(EventType.ERROR, lambda err: logger.error("error: %s", err))
        connection.on(EventType.OPEN, lambda _: logger.info("WebSocket connected."))
        connection.on(EventType.CLOSE, lambda _: logger.info("WebSocket closed."))

    async def _run_active_stream_session(
        self,
        *,
        pre_roll_frames: list[bytes],
        mic_queue: asyncio.Queue[bytes],
        mic_diag: dict[str, float | int],
    ) -> None:
        """Run one active-mode websocket session and stream all mic audio to Deepgram."""
        stream_state = {"last_deepgram_speech_at": time.time()}
        async with self._client.listen.v2.connect(
            **self._build_hotword_options()
        ) as connection:
            self._attach_hotword_ws_handlers(connection, stream_state)
            listen_task = asyncio.create_task(connection.start_listening())
            send_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=100)
            sender_task = asyncio.create_task(
                self._ws_sender(connection, send_queue, strict=True)
            )

            async def enqueue(data: bytes, context: str) -> None:
                if sender_task.done() and not sender_task.cancelled():
                    exc = sender_task.exception()
                    if exc is not None:
                        raise exc
                try:
                    send_queue.put_nowait(data)
                except asyncio.QueueFull:
                    logger.warning("[active] send_queue full — dropping frame (%s)", context)

            last_mic_chunk_at = time.monotonic()
            last_stall_log_at = 0.0
            mic_stall_active = False
            for pre_raw in pre_roll_frames:
                await enqueue(pre_raw, "active pre-roll frame")

            try:
                while self.running:
                    now = time.time()
                    deepgram_silence = now - stream_state["last_deepgram_speech_at"]
                    if deepgram_silence >= DEFAULT_ACTIVE_DISCONNECT_AFTER_SEC:
                        logger.info(
                            "[active] No Deepgram transcript for %.1fs -> disconnect websocket and switch to silence mode.",
                            deepgram_silence,
                        )
                        return

                    try:
                        raw = await asyncio.wait_for(mic_queue.get(), timeout=0.2)
                    except asyncio.TimeoutError:
                        stalled = time.monotonic() - last_mic_chunk_at
                        if stalled >= MIC_STALL_WARN_AFTER_SEC:
                            now_mono = time.monotonic()
                            if (
                                not mic_stall_active
                                or (now_mono - last_stall_log_at) >= MIC_STALL_WARN_REPEAT_SEC
                            ):
                                producer_idle = now_mono - float(mic_diag["last_portaudio_cb_mono"])
                                if producer_idle >= MIC_RECONNECT_AFTER_SEC:
                                    logger.error(
                                        "[active] Mic stall recovery: PortAudio callback silent for %.1fs "
                                        "(device_id=%s, cb_total=%d). Reconnecting hotword WS/mic...",
                                        producer_idle,
                                        self.device_id,
                                        int(mic_diag["portaudio_cb_count"]),
                                    )
                                    raise MicStallDisconnect(
                                        f"PortAudio callback silent for {producer_idle:.1f}s"
                                    )
                                logger.warning(
                                    "[active] No microphone chunks for %.1fs (device_id=%s, cb_total=%d).",
                                    stalled,
                                    self.device_id,
                                    int(mic_diag["portaudio_cb_count"]),
                                )
                                last_stall_log_at = now_mono
                                mic_stall_active = True
                        continue

                    now_mono = time.monotonic()
                    if mic_stall_active:
                        logger.info(
                            "[active] Microphone audio resumed after %.1fs without chunks.",
                            now_mono - last_mic_chunk_at,
                        )
                        mic_stall_active = False
                    last_mic_chunk_at = now_mono
                    await enqueue(raw, "active stream frame")
            finally:
                await send_queue.put(None)
                try:
                    await asyncio.wait_for(sender_task, timeout=5.0)
                except asyncio.TimeoutError:
                    sender_task.cancel()
                    await asyncio.gather(sender_task, return_exceptions=True)

                listen_task.cancel()
                try:
                    await listen_task
                except asyncio.CancelledError:
                    pass

    async def _run_hotword_mic_send_loop(
        self,
        *,
        mic_queue: asyncio.Queue[bytes],
        mic_diag: dict[str, float | int],
        sd_callback,
    ) -> None:
        """Main two-mode loop.

        - silence mode: run STE-VAD only to decide when to start websocket.
        - active mode: stream all chunks to Deepgram and use Deepgram silence timing.
        """
        mode = "silence"
        pre_roll_max_frames = max(
            1, int(round((self.sample_rate * DEFAULT_PREROLL_SECONDS) / self.blocksize))
        )
        pre_roll_buffer: deque[bytes] = deque(maxlen=pre_roll_max_frames)

        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.blocksize,
                dtype="int16",
                channels=self.channels,
                device=self.device_id,
                callback=sd_callback,
            ):
                logger.info("[silence] Mic open. Waiting for voice trigger...")
                last_mic_chunk_at = time.monotonic()
                last_stall_log_at = 0.0
                mic_stall_active = False

                while self.running:
                    try:
                        raw = await asyncio.wait_for(mic_queue.get(), timeout=0.2)
                    except asyncio.TimeoutError:
                        stalled = time.monotonic() - last_mic_chunk_at
                        if stalled >= MIC_STALL_WARN_AFTER_SEC:
                            now_mono = time.monotonic()
                            if (
                                not mic_stall_active
                                or (now_mono - last_stall_log_at) >= MIC_STALL_WARN_REPEAT_SEC
                            ):
                                producer_idle = now_mono - float(mic_diag["last_portaudio_cb_mono"])
                                if producer_idle >= MIC_RECONNECT_AFTER_SEC:
                                    logger.error(
                                        "[%s] Mic stall recovery: PortAudio callback silent for %.1fs "
                                        "(device_id=%s, cb_total=%d). Reconnecting hotword WS/mic...",
                                        mode,
                                        producer_idle,
                                        self.device_id,
                                        int(mic_diag["portaudio_cb_count"]),
                                    )
                                    raise MicStallDisconnect(
                                        f"PortAudio callback silent for {producer_idle:.1f}s"
                                    )

                                logger.warning(
                                    "[%s] No microphone audio chunks for %.1fs (device_id=%s). "
                                    "[portaudio_cb_total=%d]",
                                    mode,
                                    stalled,
                                    self.device_id,
                                    int(mic_diag["portaudio_cb_count"]),
                                )
                                last_stall_log_at = now_mono
                                mic_stall_active = True
                        continue

                    now_mono = time.monotonic()
                    if mic_stall_active:
                        logger.info(
                            "[%s] Microphone audio resumed after %.1fs without chunks.",
                            mode,
                            now_mono - last_mic_chunk_at,
                        )
                        mic_stall_active = False
                    last_mic_chunk_at = now_mono

                    if mode != "silence":
                        continue

                    vad_threshold = self.silence_rms_threshold * DEFAULT_SILENCE_STE_RATIO
                    is_voice = self.check_vad_by_using_ste(raw, silence_rms_threshold=vad_threshold)
                    pre_roll_buffer.append(raw)

                    if is_voice:
                        mode = "active"
                        logger.info(
                            "[mode] silence -> active (voice detected by STE ratio=%.2f).",
                            DEFAULT_SILENCE_STE_RATIO,
                        )
                        try:
                            await self._run_active_stream_session(
                                pre_roll_frames=list(pre_roll_buffer),
                                mic_queue=mic_queue,
                                mic_diag=mic_diag,
                            )
                        finally:
                            pre_roll_buffer.clear()
                        mode = "silence"
                        logger.info("[mode] active -> silence (active session finished).")
        finally:
            logger.info("Hotword mic loop stopped.")

    async def _start_async(self) -> None:
        logger.info("Connecting (device=%s)", self.device_id)
        loop = asyncio.get_event_loop()
        mic_queue, mic_diag, sd_callback = self._make_mic_queue_and_callback(loop)
        await self._run_hotword_mic_send_loop(
            mic_queue=mic_queue,
            mic_diag=mic_diag,
            sd_callback=sd_callback,
        )

    def start(self) -> None:
        """Start the hotword loop and automatically retry on any error. Blocks until stopped."""
        self.running = True
        retry_delay = 2.0
        max_delay = 30.0

        while self.running:
            try:
                asyncio.run(self._start_async())
                break
            except SilenceModeDisconnect as exc:
                if not self.running:
                    break
                logger.info("Hotword reconnect requested: %s", exc)
                retry_delay = 2.0
                continue
            except MicStallDisconnect as exc:
                if not self.running:
                    break
                logger.info("Hotword reconnect requested (mic stall): %s", exc)
                retry_delay = 2.0
                continue
            except Exception as exc:
                if not self.running:
                    break
                logger.warning(
                    "Hotword loop error (%s: %s). Retrying in %.1fs...",
                    type(exc).__name__,
                    exc,
                    retry_delay,
                )
                deadline = time.time() + retry_delay
                while self.running and time.time() < deadline:
                    time.sleep(0.2)
                retry_delay = min(retry_delay * 2, max_delay)

    def stop(self) -> None:
        self.running = False

    def _clear_queue_nowait(self, q) -> int:
        """Drain any queued items without blocking."""
        cleared = 0
        while True:
            try:
                q.get_nowait()
                cleared += 1
            except Exception:
                break
        return cleared

    async def _drain_thread_queue_to_async_queue(
        self, thread_q: queue.Queue[bytes], async_q: asyncio.Queue[bytes]
    ) -> None:
        """Forward audio frames from thread queue into asyncio queue."""
        while True:
            try:
                raw = thread_q.get_nowait()
                try:
                    async_q.put_nowait(raw)
                except asyncio.QueueFull:
                    logger.warning("async_q full — dropping frame in drain")
            except queue.Empty:
                await asyncio.sleep(0.02)

    def _make_task_separator_silence(self) -> bytes:
        return np.zeros(
            int(self.sample_rate * self.channels * DEFAULT_TASK_SEPARATOR_SILENCE_SECONDS),
            dtype=np.int16,
        ).tobytes()

    async def _listen_async(self, patience: int) -> str:
        accumulator = FluxListenTaskAccumulator(
            post_eot_empty_silence_sec=float(patience),
        )
        retry_delay = LISTEN_RETRY_BASE_DELAY
        thread_q: queue.Queue[bytes] = queue.Queue(maxsize=1000)
        self.register_queue(thread_q)

        try:
            for attempt in range(LISTEN_MAX_RETRIES):
                accumulator.reset()
                async_q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=1000)
                drain_task = asyncio.create_task(
                    self._drain_thread_queue_to_async_queue(thread_q, async_q)
                )

                try:
                    async with self._client.listen.v2.connect(
                        **self._build_task_options()
                    ) as connection:
                        connection.on(EventType.MESSAGE, accumulator.handle_message)
                        connection.on(
                            EventType.ERROR,
                            lambda err: logger.error("listen error: %s", err),
                        )

                        listen_task = asyncio.create_task(connection.start_listening())
                        task_send_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=200)
                        task_sender = asyncio.create_task(
                            self._ws_sender(connection, task_send_queue)
                        )

                        async def task_enqueue(data: bytes, context: str) -> None:
                            if task_sender.done() and not task_sender.cancelled():
                                exc = task_sender.exception()
                                if exc is not None:
                                    raise exc
                            try:
                                task_send_queue.put_nowait(data)
                            except asyncio.QueueFull:
                                logger.warning(
                                    "task send_queue full — dropping frame (%s)", context
                                )

                        cleared_thread = self._clear_queue_nowait(thread_q)
                        cleared_async = self._clear_queue_nowait(async_q)
                        if cleared_thread or cleared_async:
                            logger.info(
                                "Task mode buffer cleared (thread_q=%d, async_q=%d).",
                                cleared_thread,
                                cleared_async,
                            )
                        task_separator_silence = self._make_task_separator_silence()
                        await task_enqueue(task_separator_silence, "listen mode task separator silence")
                        session_start = time.time()
                        logger.info(
                            "Listening (Flux EOT sentences + %.1fs empty new-turn, max %.0fs)...",
                            float(patience),
                            self.max_task_duration,
                        )

                        try:
                            while self.running:
                                now = time.time()
                                if accumulator.should_finalize_task():
                                    logger.info(
                                        "Post-EOT empty new-turn silence %.1fs — end session.",
                                        float(patience),
                                    )
                                    break
                                if (now - session_start) > self.max_task_duration:
                                    logger.warning(
                                        "Task session exceeded max duration %.0fs — ending.",
                                        self.max_task_duration,
                                    )
                                    break

                                try:
                                    raw = await asyncio.wait_for(async_q.get(), timeout=0.2)
                                except asyncio.TimeoutError:
                                    continue

                                denoised = await self._denoise_async(raw)
                                await task_enqueue(denoised, "listen mode")
                        finally:
                            await task_send_queue.put(None)
                            try:
                                await asyncio.wait_for(task_sender, timeout=5.0)
                            except asyncio.TimeoutError:
                                task_sender.cancel()
                                await asyncio.gather(task_sender, return_exceptions=True)

                            listen_task.cancel()
                            try:
                                await listen_task
                            except asyncio.CancelledError:
                                pass

                    break  # completed without error

                except Exception as exc:
                    if attempt < LISTEN_MAX_RETRIES - 1:
                        logger.warning(
                            "Listen WS error (attempt %d/%d: %s). Retrying in %.1fs...",
                            attempt + 1,
                            LISTEN_MAX_RETRIES,
                            exc,
                            retry_delay,
                        )
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        logger.error(
                            "Listen failed after %d attempts: %s",
                            LISTEN_MAX_RETRIES,
                            exc,
                        )
                finally:
                    drain_task.cancel()
                    try:
                        await drain_task
                    except asyncio.CancelledError:
                        pass
        finally:
            self.unregister_queue(thread_q)

        task = accumulator.finalize()
        if task:
            logger.info("Task: '%s'", task)
        else:
            logger.info("No command detected.")
        return task

    def listen(self, patience: int = DEFAULT_PATIENCE_SECONDS) -> str:
        """Synchronous wrapper around `_listen_async()`."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "listen() cannot run inside an existing event loop. "
                "Use `await _listen_async(...)` from async code."
            )
        return asyncio.run(self._listen_async(patience))


class DeepgramAudioCaptureService(BaseAudioCaptureService):
    """
    Background audio capture service backed by Deepgram Flux.

    - Live microphone hotword loop: Deepgram streaming WebSocket (v2).
    - External audio transcription: Deepgram prerecorded endpoint (v1 API wrapper).
    """

    engine_name = "deepgram"

    def __init__(
        self,
        device_id: int | str | None = None,
        hotwords: list[str] | None = None,
        patience: int = DEFAULT_PATIENCE_SECONDS,
        api_key: str = "",
        model: str = DEFAULT_DEEPGRAM_MODEL,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        name: str | None = None,
        client_denoise: bool = False,
        max_task_duration: float = DEFAULT_MAX_TASK_DURATION_SECONDS,
    ) -> None:
        super().__init__(
            device_id=device_id,
            hotwords=hotwords or list(DEFAULT_HOTWORDS),
            patience=patience,
            sample_rate=sample_rate,
            channels=channels,
            name=name,
        )
        self._api_key = api_key or ""
        self._model = model
        self._client_denoise = client_denoise
        self._max_task_duration = max_task_duration
        self._transcribe_client = AsyncDeepgramClient(api_key=self._api_key)
        self._transcribe_timeout = TRANSCRIBE_TIMEOUT

    def _create_device(self) -> DeepgramFluxAudioCaptureDevice:
        return DeepgramFluxAudioCaptureDevice(
            device_id=self._device_id,
            api_key=self._api_key,
            model=self._model,
            sample_rate=self._sample_rate,
            channels=self._channels,
            name=self._name,
            hotwords=list(self._hotwords),
            client_denoise=self._client_denoise,
            max_task_duration=self._max_task_duration,
        )

    def _decode_to_wav(self, audio_data: bytes, audio_format: str) -> bytes:
        """Decode + resample audio to WAV 16-bit mono."""
        from pydub import AudioSegment

        audio = AudioSegment.from_file(io.BytesIO(audio_data), format=audio_format)
        audio = audio.set_frame_rate(self._sample_rate).set_channels(1).set_sample_width(2)
        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        return wav_io.getvalue()

    async def _transcribe_async(self, audio_data: bytes, audio_format: str) -> list[str]:
        loop = asyncio.get_running_loop()

        wav_bytes = await asyncio.wait_for(
            loop.run_in_executor(None, self._decode_to_wav, audio_data, audio_format),
            timeout=self._transcribe_timeout,
        )

        response = await asyncio.wait_for(
            self._transcribe_client.listen.v1.media.transcribe_file(
                request=wav_bytes,
                model=DEFAULT_TRANSCRIPTION_MODEL,
                smart_format=True,
            ),
            timeout=self._transcribe_timeout,
        )

        sentences: list[str] = []
        try:
            raw = getattr(response, "transcript", None)
            if raw is None:
                raw = response.results.channels[0].alternatives[0].transcript
            transcript = (raw or "").strip()
            if transcript:
                sentences.append(transcript)
        except (AttributeError, IndexError, KeyError) as exc:
            logger.warning("[AudioCapture:deepgram] transcribe_audio parse error: %s", exc)
            logger.warning("[AudioCapture:deepgram] raw response: %s", response)

        if sentences:
            logger.info("Transcribed %d sentence(s) from external audio.", len(sentences))
            with self._tasks_lock:
                self._tasks.extend(sentences)

        return sentences

    def transcribe_audio(self, audio_data: bytes, audio_format: str) -> list[str]:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "transcribe_audio() cannot run inside an existing event loop. "
                "Use `await _transcribe_async(...)` from async code."
            )
        return asyncio.run(self._transcribe_async(audio_data, audio_format))