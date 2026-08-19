import os
import pwd

try:
    uid = pwd.getpwnam("ubuntu").pw_uid
    os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
    os.environ["PULSE_RUNTIME_PATH"] = f"/run/user/{uid}/pulse"
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
    os.environ["PULSE_SERVER"] = f"unix:/run/user/{uid}/pulse/native"
except Exception:
    pass

import asyncio
import logging
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import AsyncGenerator, Generator, Optional

import numpy as np
import numpy.typing as npt
import sounddevice as sd
import soundfile as sf
import soxr

from models.response import Response

logger = logging.getLogger("Speaker:SpeakerDeviceBase")


def _set_alsa_mixer_volume(volume_percent: int) -> None:
    """Set ALSA mixer volume and unmute using amixer. Tries common mixer control names."""
    volume_percent = max(0, min(100, volume_percent))
    controls = ["Master", "Speaker", "PCM", "Headphone"]
    success_controls = []
    for control in controls:
        try:
            # Set volume and unmute in one command
            result = subprocess.run(
                ["amixer", "sset", control, f"{volume_percent}%", "unmute"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                success_controls.append(control)
                logger.info(
                    "ALSA mixer '%s' set to %d%% (unmuted)", control, volume_percent
                )
        except FileNotFoundError:
            logger.debug("amixer not found, skipping ALSA mixer volume setup")
            return
        except Exception as e:
            logger.debug("Failed to set ALSA mixer '%s': %s", control, e)

    if success_controls:
        logger.info("ALSA mixer controls configured: %s", success_controls)
    else:
        logger.warning("Could not set ALSA mixer volume. Tried controls: %s", controls)


SAMPLE_RATE = 48000
RECORDED_AUDIO_INTER_PLAY_DELAY_S = 0.3
_PA_INVALID_CHANNELS = -9998


def resolve_output_device_id(device_id: int | str | None) -> tuple[int, str]:
    """
    Validate and resolve an output audio device ID.

    - If device_id is None → auto-pick the best hardware speaker:
        * Excludes virtual devices (pipewire, pulse, etc.)
        * Excludes devices with input channels (mic arrays, combo devices)
        * If exactly one pure hardware speaker found → use it automatically
        * Otherwise → fall back to first output device found
    - If device_id is provided as an int or a str that can be int → use as index.
    - If device_id is str that cannot be converted to int → search device by name substring (case-insensitive).
      If found, pick that device.
    - If device_id is invalid/unavailable → log a warning and fall back to auto-pick.
    Returns (device_id, device_name).
    Raises RuntimeError if no output devices are found at all.
    """
    VIRTUAL_DEVICE_NAMES = {
        "pipewire",
        "pulse",
        "default",
        "dmix",
        "surround",
        "respeaker",
    }

    devices = sd.query_devices()
    logger.info(f"All Queried Output Devices: {devices}")
    all_output_ids = []
    hardware_ids = []
    for i, d in enumerate(devices):
        if d["max_output_channels"] > 0:
            all_output_ids.append(i)
            virtual = d["name"].strip().lower() in VIRTUAL_DEVICE_NAMES
            has_input = d["max_input_channels"] > 0
            if not virtual and not has_input:
                hardware_ids.append(i)

    if not all_output_ids:
        raise RuntimeError("No output audio devices found on this system.")

    def _auto_pick() -> tuple[int, str]:
        candidates = hardware_ids if hardware_ids else all_output_ids
        if len(hardware_ids) == 1:
            chosen = hardware_ids[0]
            logger.info(
                f"Auto-selected hardware speaker [{chosen}]: {devices[chosen]['name']}"
            )
            return chosen, devices[chosen]["name"]
        chosen = candidates[0]
        logger.info(
            "Auto-selected output device: [%d] %s (in=%d, out=%d, sr=%d)",
            chosen,
            devices[chosen]["name"],
            devices[chosen]["max_input_channels"],
            devices[chosen]["max_output_channels"],
            devices[chosen]["default_samplerate"],
        )
        return chosen, devices[chosen]["name"]

    if device_id is None:
        logger.info("No output device_id specified, auto-picking hardware speaker.")
        return _auto_pick()

    # Try convert to int: if int or str of int, use old logic
    int_candidate = None
    if isinstance(device_id, int) or (
        isinstance(device_id, str) and device_id.isdigit()
    ):
        int_candidate = int(device_id)
    elif isinstance(device_id, str):
        try:
            int_candidate = int(device_id)
        except Exception:
            int_candidate = None
    if int_candidate is not None:
        try:
            info = sd.query_devices(int_candidate, "output")
            if info.get("max_output_channels", 0) > 0:
                return int_candidate, info["name"]
            raise ValueError("Device has no output channels")
        except Exception as e:
            logger.warning(
                "Output device_id=%s is invalid or unavailable (%s). Falling back.",
                device_id,
                e,
            )
            return _auto_pick()

    # device_id is str but not convertable to int: try search in device names
    if isinstance(device_id, str):
        # Case-insensitive search
        device_id_lower = device_id.strip().lower()
        for i, d in enumerate(devices):
            if d["max_output_channels"] > 0 and device_id_lower in d["name"].lower():
                logger.info("Selected output device by name: [%d] %s", i, d["name"])
                return i, d["name"]
        logger.warning(
            "No output device contains name '%s'. Falling back to auto-pick.", device_id
        )
        return _auto_pick()

    # fallback
    logger.warning(
        "Output device_id=%s is invalid or unavailable. Falling back.", device_id
    )
    return _auto_pick()


def _resolve_output_channels(device_id: int, requested_channels: int) -> int:
    """
    Resolve channel count for OutputStream. Some devices (e.g. macOS speakers)
    do not support mono (1 channel) and require stereo (2 channels).
    """
    try:
        info = sd.query_devices(device_id, "output")
        max_ch = info.get("max_output_channels", 2)
        if requested_channels <= max_ch:
            return requested_channels
        logger.debug(
            "Device %s supports max %d output channels, using that (requested %d)",
            device_id,
            max_ch,
            requested_channels,
        )
        return max_ch
    except Exception as e:
        logger.warning(
            "Could not query device %s: %s. Using requested channels.", device_id, e
        )
        return requested_channels


def _create_output_stream(
    device_id: int,
    samplerate: int,
    channels: int,
    dtype: type,
    blocksize: int,
) -> tuple[sd.OutputStream, int]:
    """
    Create OutputStream with channel fallback. If device rejects mono (channels=1),
    retry with stereo (2) since many output devices require it.
    Returns (stream, actual_channels_used).
    """
    resolved = _resolve_output_channels(device_id, channels)

    logger.debug(
        "[SPEAKER_STREAM_CREATE] device_id=%s(%s) samplerate=%d channels=%d→%d dtype=%s blocksize=%d",
        device_id,
        type(device_id).__name__,
        samplerate,
        channels,
        resolved,
        dtype,
        blocksize,
    )
    try:
        stream = sd.OutputStream(
            samplerate=samplerate,
            channels=resolved,
            dtype=dtype,
            blocksize=blocksize,
            device=device_id,
        )
        return stream, resolved
    except sd.PortAudioError as e:
        err_code = e.args[1] if len(e.args) > 1 else None
        if resolved == 1 and err_code == _PA_INVALID_CHANNELS:
            logger.info(
                "Device %s does not support mono, falling back to stereo", device_id
            )
            stream = sd.OutputStream(
                samplerate=samplerate,
                channels=2,
                dtype=dtype,
                blocksize=blocksize,
                device=device_id,
            )
            return stream, 2
        raise


INPUT_SAMPLE_RATE = 24000


def _normalize_audio(
    audio: np.ndarray, sr: int, target_sample_rate: int, target_channels: int
) -> np.ndarray:
    """Resample and convert channels to match the output stream."""
    if audio.ndim == 1:
        audio = audio.reshape(-1, 1)

    file_channels = audio.shape[1]
    if file_channels != target_channels:
        if target_channels == 1:
            audio = audio.mean(axis=1, keepdims=True)
        else:
            audio = np.repeat(
                audio.mean(axis=1, keepdims=True), target_channels, axis=1
            )

    if sr != target_sample_rate:
        audio = soxr.resample(audio, sr, target_sample_rate)

    return audio.astype(np.float32)


def _wav_chunks_sync(
    file_path: str,
    target_sample_rate: int = SAMPLE_RATE,
    target_channels: int = 1,
    block_size: int = 4096,
    whole_file: bool = False,
) -> Generator[npt.NDArray[np.float32], None, None]:
    """Read a WAV file and yield resampled float32 chunks (sync generator).

    If whole_file is True, yield a single chunk after normalize (fewer OutputStream
    writes — smoother for short recorded clips on embedded hardware).
    """
    audio, sr = sf.read(file_path, dtype="float32")
    audio = _normalize_audio(audio, sr, target_sample_rate, target_channels)

    if whole_file:
        if len(audio) > 0:
            yield audio
        return

    for i in range(0, len(audio), block_size):
        chunk = audio[i : i + block_size]
        if len(chunk) > 0:
            yield chunk


async def _wav_chunks_async(
    file_path: str,
    target_sample_rate: int = SAMPLE_RATE,
    target_channels: int = 1,
    block_size: int = 4096,
    whole_file: bool = False,
) -> AsyncGenerator[npt.NDArray[np.float32], None]:
    """Read a WAV file and yield resampled float32 chunks (async generator)."""
    audio, sr = await asyncio.to_thread(sf.read, file_path, dtype="float32")
    audio = await asyncio.to_thread(
        _normalize_audio, audio, sr, target_sample_rate, target_channels
    )

    if whole_file:
        if len(audio) > 0:
            yield audio
        return

    for i in range(0, len(audio), block_size):
        chunk = audio[i : i + block_size]
        if len(chunk) > 0:
            yield chunk


def _wav_chunks_sync_times(
    file_path: str,
    target_sample_rate: int,
    target_channels: int,
    block_size: int,
    times: int,
    whole_file: bool = False,
) -> Generator[npt.NDArray[np.float32], None, None]:
    """
    Yield WAV chunks repeated `times` times (sync generator).

    Each repeat is independent: one pass through `_wav_chunks_sync` per repeat
    (with whole_file=True, one yield = one full clip per repeat), not one
    concatenated buffer for all repeats. Between repeats, sleeps
    ``RECORDED_AUDIO_INTER_PLAY_DELAY_S``.
    """
    safe_times = max(1, int(times))
    for i in range(safe_times):
        yield from _wav_chunks_sync(
            file_path,
            target_sample_rate=target_sample_rate,
            target_channels=target_channels,
            block_size=block_size,
            whole_file=whole_file,
        )
        if i < safe_times - 1:
            time.sleep(RECORDED_AUDIO_INTER_PLAY_DELAY_S)


async def _wav_chunks_async_times(
    file_path: str,
    target_sample_rate: int,
    target_channels: int,
    block_size: int,
    times: int,
    whole_file: bool = False,
) -> AsyncGenerator[npt.NDArray[np.float32], None]:
    """
    Yield WAV chunks repeated `times` times (async generator).

    Same semantics as ``_wav_chunks_sync_times``: each repeat is a separate
    full clip (not one merged buffer for all repeats).
    """
    safe_times = max(1, int(times))
    for i in range(safe_times):
        async for chunk in _wav_chunks_async(
            file_path,
            target_sample_rate=target_sample_rate,
            target_channels=target_channels,
            block_size=block_size,
            whole_file=whole_file,
        ):
            yield chunk
        if i < safe_times - 1:
            await asyncio.sleep(RECORDED_AUDIO_INTER_PLAY_DELAY_S)


class SpeakerDeviceBase:
    runable: bool = True

    def __init__(
        self,
        device_id: int | None = None,
        name: str | None = None,
        sample_rate: int = SAMPLE_RATE,
        block_size: int = 1024,
        channels: int = 1,
        dtype: type = np.float32,
        volume: float = 1.0,
        fade_in_ms: int = 0,
        startup_delay_ms: int = 0,
        mixer_volume: int = 100,
    ):
        logger.info(f"Resolving device ID received: {device_id}")
        self.device_id, resolved_name = resolve_output_device_id(device_id)
        logger.info(f"Resolved device ID: {self.device_id}, {resolved_name}")
        self.device_name = name or resolved_name
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.channels = channels
        self.dtype = dtype
        self.should_stop = False
        self.volume = float(np.clip(volume, 0.0, 2.0))
        self.fade_in_ms = max(fade_in_ms, 0)
        self.startup_delay_ms = max(startup_delay_ms, 0)
        self._is_first_write = True

        # Set ALSA hardware mixer volume on init
        _set_alsa_mixer_volume(mixer_volume)

        logger.info(
            "Speaker init: device=%s, volume=%.2f, mixer=%d%%, fade_in=%dms, startup_delay=%dms",
            self.device_id,
            self.volume,
            mixer_volume,
            self.fade_in_ms,
            self.startup_delay_ms,
        )

    def _apply_volume_and_fade(self, chunk: np.ndarray, is_first: bool) -> np.ndarray:
        """Apply master volume and fade-in envelope to audio chunk."""
        if is_first and self.fade_in_ms > 0:
            fade_samples = int(self.sample_rate * self.fade_in_ms / 1000)
            fade_len = min(fade_samples, len(chunk))
            envelope = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
            if chunk.ndim == 2:
                envelope = envelope.reshape(-1, 1)
            chunk = chunk.copy()
            chunk[:fade_len] *= envelope

        if self.volume != 1.0:
            chunk = (chunk * np.float32(self.volume)).clip(
                np.float32(-1.0), np.float32(1.0)
            )

        return chunk

    def _try_write(self, chunk: np.ndarray) -> None:
        """Write audio chunk with volume/fade-in and automatic stream recovery."""
        is_first = self._is_first_write
        if is_first:
            self._is_first_write = False
            if self.startup_delay_ms > 0:
                logger.debug("[SPEAKER] startup delay %dms", self.startup_delay_ms)
                time.sleep(self.startup_delay_ms / 1000.0)

        chunk = self._apply_volume_and_fade(chunk, is_first)
        try:
            self.stream.write(chunk)
        except sd.PortAudioError as e:
            logger.warning(
                "PortAudio write error: %s. Attempting stream recovery...", e
            )
            try:
                self.stream.stop()
                self.stream.start()
                self.stream.write(chunk)
                logger.info("Stream recovered successfully.")
            except Exception as recover_err:
                logger.error("Stream recovery failed: %s", recover_err)
                raise

    def _adapt_channels(self, chunk: np.ndarray) -> np.ndarray:
        """Ensure chunk channel count matches self.channels for the OutputStream."""
        if chunk.ndim == 1:
            chunk = chunk.reshape(-1, 1)
        chunk_ch = chunk.shape[1]
        if chunk_ch == self.channels:
            return chunk
        if self.channels == 1:
            return chunk.mean(axis=1, keepdims=True)
        return np.repeat(chunk.mean(axis=1, keepdims=True), self.channels, axis=1)

    def speak(self, text: str, interrupt: bool = False) -> Optional[Response]:
        """Speak the given text (sync mode)

        Calling this only add the text to queue (i.e. no wait)
        """
        raise NotImplementedError

    async def aspeak(self, text: str, interrupt: bool = False) -> Optional[Response]:
        """Speak the given text (async mode)

        Calling this will add the text to queue and wait until it finishes speaking
        """
        raise NotImplementedError

    def play_file(
        self, file_path: str, times: int = 1, interrupt: bool = False
    ) -> Optional[Response]:
        """Play audio from a WAV file (sync mode, fire-and-forget)"""
        raise NotImplementedError

    async def aplay_file(
        self, file_path: str, times: int = 1, interrupt: bool = False
    ) -> Optional[Response]:
        """Play audio from a WAV file (async mode, wait until finished)"""
        raise NotImplementedError


class SyncSpeakerDeviceBase(SpeakerDeviceBase):
    def is_healthy(self) -> bool:
        """Return True if the audio output stream is active."""
        try:
            return self.stream is not None and self.stream.active
        except Exception:
            return False

    def restart(self) -> None:
        """Reset the audio output stream."""
        self._reset_stream()

    def __init__(
        self,
        device_id: int | None = None,
        name: str | None = None,
        sample_rate: int = SAMPLE_RATE,
        block_size: int = 1024,
        channels: int = 1,
        chunk_write_timeout: float = 10.0,
        volume: float = 1.0,
        fade_in_ms: int = 0,
        startup_delay_ms: int = 0,
        mixer_volume: int = 100,
    ):
        super().__init__(
            device_id,
            name,
            sample_rate,
            block_size,
            channels,
            volume=volume,
            fade_in_ms=fade_in_ms,
            startup_delay_ms=startup_delay_ms,
            mixer_volume=mixer_volume,
        )
        self._chunk_write_timeout = chunk_write_timeout

        self.play_stream_tasks: set[asyncio.Task] = set()
        self.interrupt_events: dict[asyncio.Task, threading.Event] = dict()
        self.sync_device_lock = threading.Lock()
        self.stream, actual_channels = _create_output_stream(
            self.device_id,
            self.sample_rate,
            self.channels,
            self.dtype,
            self.block_size,
        )
        self.channels = actual_channels
        self.stream.start()

    def __del__(self):
        self.stream.stop()
        self.stream.close()

    def _reset_stream(self) -> None:
        """Close and reopen the OutputStream to recover from a stuck stream."""
        logger.warning(
            "Resetting audio output stream on device %s (sync)", self.device_id
        )
        for method in (self.stream.abort, self.stream.close):
            try:
                method()
            except Exception as e:
                logger.debug("stream.%s() during reset: %s", method.__name__, e)

        self.stream, self.channels = _create_output_stream(
            self.device_id,
            self.sample_rate,
            self.channels,
            self.dtype,
            self.block_size,
        )
        self.stream.start()
        self._is_first_write = True
        logger.info(
            "Audio output stream reset successfully on device %s (sync)", self.device_id
        )

    def _play_stream(
        self,
        buffer_stream: Generator[np.ndarray, None, None],
        interrupt_event: threading.Event,
    ):
        """Play audio stream (sync mode).

        Polls for the device lock with a short timeout so the interrupt flag
        is checked regularly.  Each individual chunk write is also guarded by
        ``self._chunk_write_timeout`` so that a hung ``stream.write()`` does not
        block the background thread forever.
        """
        while True:
            if interrupt_event.is_set():
                logger.debug("[SPEAKER_SYNC] interrupted before lock acquire")
                break

            if self.sync_device_lock.acquire(timeout=0.1):
                need_reset = False
                bail_fast = False
                executor: ThreadPoolExecutor | None = None
                try:
                    # One worker thread for all chunks: avoids spawning a thread per
                    # chunk (very janky on embedded) while keeping per-write timeout.
                    executor = ThreadPoolExecutor(max_workers=1)
                    for chunk in buffer_stream:
                        if interrupt_event.is_set():
                            logger.debug("[SPEAKER_SYNC] interrupted during playback")
                            break
                        adapted = self._adapt_channels(chunk)
                        fut = executor.submit(self._try_write, adapted)
                        try:
                            fut.result(timeout=self._chunk_write_timeout)
                        except FuturesTimeoutError:
                            logger.error(
                                "[SPEAKER_SYNC] stream.write() timed out after %.1fs – will reset stream",
                                self._chunk_write_timeout,
                            )
                            need_reset = True
                            bail_fast = True
                            break
                        except Exception as exc:
                            logger.error(
                                "[SPEAKER_SYNC] write error: %s – will reset stream",
                                exc,
                            )
                            need_reset = True
                            bail_fast = True
                            break
                finally:
                    if executor is not None:
                        # Hung stream.write() must not block shutdown(wait=True) forever.
                        executor.shutdown(wait=not bail_fast, cancel_futures=bail_fast)
                    self.sync_device_lock.release()
                if need_reset:
                    self._reset_stream()
                break

    def _add_new_task(
        self, buffer_stream: Generator[np.ndarray, None, None], interrupt: bool = False
    ):
        """Add new streaming task"""

        if interrupt:
            self.interrupt_all_task()

        interrupt_event = threading.Event()
        task = asyncio.create_task(
            asyncio.to_thread(self._play_stream, buffer_stream, interrupt_event)
        )
        self.play_stream_tasks.add(task)
        self.interrupt_events[task] = interrupt_event

        def done_call_back(t: asyncio.Task):
            self.play_stream_tasks.discard(t)
            del self.interrupt_events[t]

        task.add_done_callback(done_call_back)

        return task

    def play_file(
        self,
        file_path: str,
        times: int = 1,
        interrupt: bool = False,
    ) -> Optional[Response]:
        safe_times = max(1, int(times))
        logger.debug("Playing WAV file: %s (times=%d)", file_path, safe_times)
        self._add_new_task(
            _wav_chunks_sync_times(
                file_path,
                self.sample_rate,
                self.channels,
                self.block_size,
                safe_times,
                whole_file=True,
            ),
            interrupt,
        )
        return Response(success=True, message="Played file successfully")

    async def aplay_file(
        self,
        file_path: str,
        times: int = 1,
        interrupt: bool = False,
        timeout: float = 60.0,
    ) -> Optional[Response]:
        safe_times = max(1, int(times))
        logger.debug("Playing WAV file: %s (times=%d)", file_path, safe_times)
        task = self._add_new_task(
            _wav_chunks_sync_times(
                file_path,
                self.sample_rate,
                self.channels,
                self.block_size,
                safe_times,
                whole_file=True,
            ),
            interrupt,
        )
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except asyncio.TimeoutError:
            self.interrupt_events.get(task, threading.Event()).set()
            try:
                await task
            except Exception:
                pass
            logger.warning(
                "File playback timed out after %.0fs: %s", timeout, file_path
            )
            return Response(
                success=False, message=f"File playback timed out after {timeout:.0f}s"
            )
        except asyncio.CancelledError:
            logger.info("File playback interrupted: %s", file_path)
            return Response(
                success=False, message=f"File playback interrupted: {file_path}"
            )
        return Response(success=True, message="Played file successfully")

    def interrupt_all_task(self):
        for t in self.play_stream_tasks:
            self.interrupt_events[t].set()

    async def await_until_finish(self):
        await asyncio.gather(*self.play_stream_tasks)


class AsyncSpeakerDeviceBase(SpeakerDeviceBase):
    def is_healthy(self) -> bool:
        """Return True if the audio output stream is active."""
        try:
            return self.stream is not None and self.stream.active
        except Exception:
            return False

    def restart(self) -> None:
        """Reset the audio output stream."""
        self._reset_stream()

    def __init__(
        self,
        device_id: int | None = None,
        name: str | None = None,
        sample_rate: int = SAMPLE_RATE,
        block_size: int = 1024,
        channels: int = 1,
        chunk_write_timeout: float = 10.0,
        lock_acquire_timeout: float = 5.0,
        volume: float = 1.0,
        fade_in_ms: int = 0,
        startup_delay_ms: int = 0,
        mixer_volume: int = 100,
    ):
        super().__init__(
            device_id,
            name,
            sample_rate,
            block_size,
            channels,
            volume=volume,
            fade_in_ms=fade_in_ms,
            startup_delay_ms=startup_delay_ms,
            mixer_volume=mixer_volume,
        )
        self._chunk_write_timeout = chunk_write_timeout
        self._lock_acquire_timeout = lock_acquire_timeout

        self.play_stream_tasks: set[asyncio.Task] = set()
        self.async_device_lock = asyncio.Lock()
        self.sync_device_lock = threading.Lock()

        self.stream, actual_channels = _create_output_stream(
            self.device_id,
            self.sample_rate,
            self.channels,
            self.dtype,
            self.block_size,
        )
        self.channels = actual_channels
        self.stream.start()

    def __del__(self):
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass

    def _reset_stream(self) -> None:
        """Close and reopen the OutputStream to recover from a stuck or broken stream.

        This is called from a background thread when a write times out or the stream
        enters an unrecoverable state.  Acquires ``sync_device_lock`` first so that
        any orphaned write thread finishes (or is unblocked by ``stream.abort()``)
        before we recreate the stream.
        """
        logger.warning("Resetting audio output stream on device %s", self.device_id)

        # Abort first to unblock any orphaned stream.write() holding sync_device_lock
        try:
            self.stream.abort()
        except Exception as e:
            logger.debug("stream.abort() during reset: %s", e)

        # Now wait for the orphaned thread to release the lock
        acquired = self.sync_device_lock.acquire(timeout=self._chunk_write_timeout)
        if not acquired:
            logger.warning(
                "sync_device_lock still held after %.1fs during reset – forcing ahead",
                self._chunk_write_timeout,
            )
        try:
            try:
                self.stream.close()
            except Exception as e:
                logger.debug("stream.close() during reset: %s", e)

            self.stream, self.channels = _create_output_stream(
                self.device_id,
                self.sample_rate,
                self.channels,
                self.dtype,
                self.block_size,
            )
            self.stream.start()
            self._is_first_write = True
            logger.info(
                "Audio output stream reset successfully on device %s", self.device_id
            )
        finally:
            if acquired:
                self.sync_device_lock.release()

    def __play_chunk(self, chunk: npt.NDArray[np.float32]) -> None:
        """Write one audio chunk to the output stream under a timed lock.

        Using a timeout instead of an unconditional ``with`` prevents a
        background thread that was orphaned by a task cancellation from
        blocking the next write indefinitely.
        """
        acquired = self.sync_device_lock.acquire(timeout=self._lock_acquire_timeout)
        if not acquired:
            logger.error(
                "Could not acquire sync_device_lock within %.1fs – skipping chunk",
                self._lock_acquire_timeout,
            )
            return
        try:
            self._try_write(self._adapt_channels(chunk))
        finally:
            self.sync_device_lock.release()

    async def _aplay_stream(
        self, buffer_stream: AsyncGenerator[npt.NDArray[np.float32], None]
    ):
        """Play audio stream (async mode).

        Each chunk write is wrapped with a hard timeout so that a hung
        ``stream.write()`` call (e.g. after device disconnect) cannot hold
        ``async_device_lock`` indefinitely and block all subsequent speaks.
        On timeout the stream is recreated so the next call succeeds.
        """
        logger.debug(
            "[SPEAKER_ASYNC] waiting for async_device_lock (timeout=%.1fs)",
            self._lock_acquire_timeout,
        )
        try:
            await asyncio.wait_for(
                self.async_device_lock.acquire(),
                timeout=self._lock_acquire_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "[SPEAKER_ASYNC] async_device_lock acquire timed out after %.1fs – skipping playback",
                self._lock_acquire_timeout,
            )
            return
        logger.debug(
            "[SPEAKER_ASYNC] async_device_lock acquired, starting chunk playback"
        )
        chunk_count = 0
        try:
            async for chunk in buffer_stream:
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(self.__play_chunk, chunk),
                        timeout=self._chunk_write_timeout,
                    )
                    chunk_count += 1
                except asyncio.TimeoutError:
                    logger.error(
                        "[SPEAKER_ASYNC] stream.write() timed out after %.1fs at chunk %d – resetting stream",
                        self._chunk_write_timeout,
                        chunk_count,
                    )
                    await asyncio.to_thread(self._reset_stream)
                    return
                except asyncio.CancelledError:
                    logger.debug("[SPEAKER_ASYNC] cancelled at chunk %d", chunk_count)
                    raise
                except Exception as e:
                    logger.error(
                        "[SPEAKER_ASYNC] write error at chunk %d: %s – resetting stream",
                        chunk_count,
                        e,
                    )
                    await asyncio.to_thread(self._reset_stream)
                    return
            logger.debug(
                "[SPEAKER_ASYNC] playback finished, %d chunks written", chunk_count
            )
        finally:
            self.async_device_lock.release()
            logger.debug("[SPEAKER_ASYNC] async_device_lock released")

    def _add_new_task(
        self, buffer_stream: AsyncGenerator[np.ndarray, None], interrupt: bool = False
    ):
        """Add new streaming task"""

        if interrupt:
            self.interrupt_all_task()

        task = asyncio.create_task(self._aplay_stream(buffer_stream))
        self.play_stream_tasks.add(task)
        task.add_done_callback(self.play_stream_tasks.discard)

        return task

    def play_file(
        self,
        file_path: str,
        times: int = 1,
        interrupt: bool = False,
    ) -> Optional[Response]:
        safe_times = max(1, int(times))
        logger.debug("Playing WAV file: %s (times=%d)", file_path, safe_times)
        self._add_new_task(
            _wav_chunks_async_times(
                file_path,
                self.sample_rate,
                self.channels,
                self.block_size,
                safe_times,
                whole_file=True,
            ),
            interrupt,
        )
        return Response(success=True, message="Played file successfully")

    async def aplay_file(
        self,
        file_path: str,
        times: int = 1,
        interrupt: bool = False,
        timeout: float = 60.0,
    ) -> Optional[Response]:
        safe_times = max(1, int(times))
        logger.debug("Playing WAV file: %s (times=%d)", file_path, safe_times)
        task = self._add_new_task(
            _wav_chunks_async_times(
                file_path,
                self.sample_rate,
                self.channels,
                self.block_size,
                safe_times,
                whole_file=True,
            ),
            interrupt,
        )
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            logger.warning(
                "File playback timed out after %.0fs: %s", timeout, file_path
            )
            return Response(
                success=False, message=f"File playback timed out after {timeout:.0f}s"
            )
        except asyncio.CancelledError:
            logger.info("File playback interrupted: %s", file_path)
            return Response(
                success=False, message=f"File playback interrupted: {file_path}"
            )
        return Response(success=True, message="Played file successfully")

    def interrupt_all_task(self):
        for t in self.play_stream_tasks:
            t.cancel()

    async def await_until_finish(self):
        await asyncio.gather(*self.play_stream_tasks)
