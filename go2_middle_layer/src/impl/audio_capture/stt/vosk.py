"""
Vosk audio capture implementation (device + service).
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import queue
import threading
import time
from typing import TYPE_CHECKING, Any

import noisereduce as nr
import numpy as np
import sounddevice as sd
from vosk import KaldiRecognizer, Model

from impl.audio_capture.base import (
    BaseAudioCaptureDevice,
    BaseAudioCaptureService,
    resolve_input_device_id,
)

logger = logging.getLogger("AudioCapture:VoskAudioCapture")

if TYPE_CHECKING:
    from vosk import Model


DEFAULT_HOTWORDS: list[str] = ["hello"]
DEFAULT_VOSK_MODEL_ID = "vosk-model-small-en-us-0.15"
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_PATIENCE_SECONDS = 3
DEFAULT_SILENCE_RMS_THRESHOLD = 0.01


class VoskAudioCaptureDevice(BaseAudioCaptureDevice):
    """
    Microphone device using Vosk for hotword detection and ASR.
    """

    def __init__(
        self,
        device_id: int | None,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        model_id: str = DEFAULT_VOSK_MODEL_ID,
        name: str | None = None,
        hotwords: list[str] | None = None,
        silence_rms_threshold: float = DEFAULT_SILENCE_RMS_THRESHOLD,
        blocksize: int = 8000,
    ) -> None:
        resolved_id, resolved_name = resolve_input_device_id(device_id)
        super().__init__(
            device_id=resolved_id,
            sample_rate=sample_rate,
            channels=channels,
            name=name or resolved_name,
        )

        self.model = Model(model_name=model_id)
        self.hotwords = hotwords or list(DEFAULT_HOTWORDS)
        self.silence_rms_threshold = silence_rms_threshold
        self.blocksize = blocksize

        # [unk] allows Vosk to accept hotword even when surrounded by other sounds
        self._hotwords_grammar = json.dumps(self.hotwords + ["[unk]"])
        self._hotword_recognizer = KaldiRecognizer(
            self.model, self.sample_rate, self._hotwords_grammar
        )

    def _denoise(self, data: bytes) -> bytes:
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        reduced = nr.reduce_noise(y=samples, sr=self.sample_rate)
        return (np.clip(reduced, -1.0, 1.0) * 32768.0).astype(np.int16).tobytes()

    def start(self) -> None:
        """
        Start the hotword detection loop (blocking).

        Callback execution is offloaded to daemon threads to keep the hotword loop
        responsive while downstream logic (e.g. `listen()`) runs.
        """
        logger.info("[VoskAudioCaptureDevice] Starting device=%s", self.device_id)
        self.running = True

        hotword_queue: queue.Queue[bytes] = queue.Queue(maxsize=200)

        def sd_callback(indata, frames, time_info, status):
            self._broadcast(indata)
            # Never block the audio callback thread.
            try:
                hotword_queue.put_nowait(bytes(indata))
            except queue.Full:
                pass

        with sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            dtype="int16",
            channels=self.channels,
            device=self.device_id,
            callback=sd_callback,
        ):
            logger.info(
                "[VoskAudioCaptureDevice] Mic open. Waiting for hotword=%s",
                self.hotwords,
            )
            while self.running:
                try:
                    raw = hotword_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                data = self._denoise(raw)
                if self._hotword_recognizer.AcceptWaveform(data):
                    result: dict[str, Any] = json.loads(
                        self._hotword_recognizer.Result()
                    )
                    text = (result.get("text", "") or "").strip().lower()
                    if text and any(hw.lower() in text for hw in self.hotwords):
                        logger.info(
                            "[VoskAudioCaptureDevice] Hotword detected: '%s'", text
                        )
                        self._hotword_recognizer.Reset()
                        if not self._try_enter_task_mode():
                            logger.info("Hotword ignored (task mode active)")
                            continue

                        def run_callbacks() -> None:
                            try:
                                for cb in list(self.callbacks):
                                    cb(text)
                            except Exception as exc:
                                logger.warning("hotword callback error: %s", exc)
                            finally:
                                self._exit_task_mode()

                        threading.Thread(target=run_callbacks, daemon=True).start()

    def stop(self) -> None:
        self.running = False

    def listen(self, patience: int = DEFAULT_PATIENCE_SECONDS) -> str:
        """
        Listen for a command after a hotword.

        Strategy:
        - Use RMS gate to keep the session alive while speech energy exists
        - Use Vosk end-of-utterance detection to emit sentence chunks
        - End the session after `patience` seconds of silence
        """
        cmd_queue: queue.Queue[bytes] = queue.Queue(maxsize=200)
        sentences: list[str] = []
        last_speech = time.time()

        recognizer = KaldiRecognizer(self.model, self.sample_rate)

        logger.info(
            "[VoskAudioCaptureDevice] Listening (ends after %ds silence)...", patience
        )
        try:
            self.register_queue(cmd_queue)
            while self.running:
                silence_dur = time.time() - last_speech
                if silence_dur > patience:
                    logger.info(
                        "[VoskAudioCaptureDevice] Silence %.1fs — end session.",
                        silence_dur,
                    )
                    break

                try:
                    raw = cmd_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                denoised = self._denoise(raw)

                samples = (
                    np.frombuffer(denoised, dtype=np.int16).astype(np.float32) / 32768.0
                )
                rms = float(np.sqrt(np.mean(samples**2)))
                if rms > self.silence_rms_threshold:
                    last_speech = time.time()

                if recognizer.AcceptWaveform(denoised):
                    text = json.loads(recognizer.Result()).get("text", "").strip()
                    if text:
                        logger.info("[VoskAudioCaptureDevice] Sentence: '%s'", text)
                        sentences.append(text)
                        last_speech = time.time()
        finally:
            tail = json.loads(recognizer.FinalResult()).get("text", "").strip()
            if tail:
                logger.info("[VoskAudioCaptureDevice] Sentence (tail): '%s'", tail)
                sentences.append(tail)
            self.unregister_queue(cmd_queue)

        task = " ".join(sentences).strip()
        if task:
            logger.info("[VoskAudioCaptureDevice] Task: '%s'", task)
        else:
            logger.info("[VoskAudioCaptureDevice] No command detected.")
        return task


class VoskAudioCaptureService(BaseAudioCaptureService):
    """
    Background audio capture service backed by Vosk.
    """

    engine_name = "vosk"

    # Timeout (seconds) for the full transcription pipeline (decode + CPU ASR).
    TRANSCRIBE_TIMEOUT: float = 30.0

    def __init__(
        self,
        device_id: int | str | None = None,
        hotwords: list[str] | None = None,
        patience: int = DEFAULT_PATIENCE_SECONDS,
        model_id: str = DEFAULT_VOSK_MODEL_ID,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        silence_threshold: float = DEFAULT_SILENCE_RMS_THRESHOLD,
        name: str | None = None,
    ) -> None:
        super().__init__(
            device_id=device_id,
            hotwords=hotwords or list(DEFAULT_HOTWORDS),
            patience=patience,
            sample_rate=sample_rate,
            channels=channels,
            name=name,
        )
        self._model_id = model_id
        self._silence_threshold = silence_threshold
        self._vosk_model: Model | None = None

    def _create_device(self) -> VoskAudioCaptureDevice:
        return VoskAudioCaptureDevice(
            device_id=self._device_id,
            sample_rate=self._sample_rate,
            channels=self._channels,
            model_id=self._model_id,
            name=self._name,
            hotwords=list(self._hotwords),
            silence_rms_threshold=self._silence_threshold,
        )

    def _get_vosk_model(self) -> "Model":
        if self._device is not None and hasattr(self._device, "model"):
            return getattr(self._device, "model")
        if self._vosk_model is None:
            from vosk import Model

            logger.info(
                "[AudioCapture:vosk] Loading Vosk model '%s' for transcription.",
                self._model_id,
            )
            self._vosk_model = Model(model_name=self._model_id)
        return self._vosk_model

    def _decode_to_pcm(self, audio_data: bytes, audio_format: str) -> bytes:
        """
        Decode and resample audio into 16-bit mono PCM.

        Args:
            audio_data: Raw audio bytes.
            audio_format: Format hint (ogg, wav, mp3, flac, webm).

        Returns:
            PCM bytes (s16le, mono) at `self._sample_rate`.
        """
        from pydub import AudioSegment

        audio = AudioSegment.from_file(io.BytesIO(audio_data), format=audio_format)
        audio = (
            audio.set_frame_rate(self._sample_rate).set_channels(1).set_sample_width(2)
        )
        return audio.raw_data

    def _recognize_pcm(self, pcm_data: bytes) -> list[str]:
        """
        Run offline Vosk recognition on 16-bit mono PCM data.

        Args:
            pcm_data: PCM bytes (s16le mono) at `self._sample_rate`.

        Returns:
            Sentence list (may be empty).
        """
        from vosk import KaldiRecognizer

        model = self._get_vosk_model()
        recognizer = KaldiRecognizer(model, self._sample_rate)

        sentences: list[str] = []
        chunk_size = int(self._sample_rate * 0.25) * 2  # ~0.25s of 16-bit mono PCM
        for offset in range(0, len(pcm_data), chunk_size):
            chunk = pcm_data[offset : offset + chunk_size]
            if recognizer.AcceptWaveform(chunk):
                text = json.loads(recognizer.Result()).get("text", "").strip()
                if text:
                    sentences.append(text)

        tail = json.loads(recognizer.FinalResult()).get("text", "").strip()
        if tail:
            sentences.append(tail)

        return sentences

    def _transcribe_sync(self, audio_data: bytes, audio_format: str) -> list[str]:
        """
        Synchronous transcription pipeline used by both sync and async entry points.

        Args:
            audio_data: Raw audio bytes.
            audio_format: Format hint (ogg, wav, mp3, flac, webm).

        Returns:
            Sentence list.
        """
        pcm_data = self._decode_to_pcm(audio_data, audio_format)
        sentences = self._recognize_pcm(pcm_data)

        if sentences:
            logger.info(
                "[AudioCapture:vosk] Transcribed %d sentence(s) from external audio.",
                len(sentences),
            )
            with self._tasks_lock:
                self._tasks.extend(sentences)

        return sentences

    def transcribe_audio(self, audio_data: bytes, audio_format: str) -> list[str]:
        """Transcribe raw audio bytes (e.g. Telegram voice message) via Vosk."""
        return self._transcribe_sync(audio_data, audio_format)

    async def _transcribe_async(
        self, audio_data: bytes, audio_format: str
    ) -> list[str]:
        """
        Async transcription wrapper for MCP usage.

        This offloads decoding (ffmpeg via pydub) and CPU-bound recognition to a worker
        thread so the event loop is not blocked. A global timeout is enforced via
        `TRANSCRIBE_TIMEOUT` for parity with the Deepgram service behavior.

        Args:
            audio_data: Raw audio bytes.
            audio_format: Format hint (ogg, wav, mp3, flac, webm).

        Returns:
            List of sentence strings.

        Raises:
            asyncio.TimeoutError: If the transcription exceeds `TRANSCRIBE_TIMEOUT`.
            Exception: Any decode/ASR errors from the sync pipeline.
        """
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, self._transcribe_sync, audio_data, audio_format),
            timeout=self.TRANSCRIBE_TIMEOUT,
        )
