from __future__ import annotations

import importlib
import logging
from pathlib import Path

from dependency_injector import containers, providers
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from paths import resolve_src_path

logger = logging.getLogger(__name__)


def _lazy_class(
    module_path: str, class_name: str, fallback: tuple[str, str] | None = None
):
    """Return a factory that lazily imports and instantiates *class_name* from *module_path*.

    When the factory is called with ``(**kwargs)`` it:
    1. Imports the module (only on first call — Python caches it).
    2. Gets the class.
    3. Returns ``cls(**kwargs)``.

    If *fallback* is provided as ``(module, class)`` and the primary import
    raises ``ImportError`` / ``Exception``, the fallback is used instead (stub pattern).
    """

    _resolved_cls: list = []  # mutable cache shared across calls

    def _factory(*args, **kwargs):
        if not _resolved_cls:
            try:
                mod = importlib.import_module(module_path)
                _resolved_cls.append(getattr(mod, class_name))
            except (ImportError, Exception) as exc:
                if fallback is None:
                    raise
                logger.info(
                    "Could not import %s.%s (%s), falling back to %s.%s",
                    module_path,
                    class_name,
                    exc,
                    fallback[0],
                    fallback[1],
                )
                mod = importlib.import_module(fallback[0])
                _resolved_cls.append(getattr(mod, fallback[1]))
        return _resolved_cls[0](*args, **kwargs)

    return _factory


class ServiceSettings(BaseSettings):
    STATE_SERVICE_MODE: str = Field(default="ros2")
    STATE_TOPIC: str = Field(default="/lf/sportmodestate")
    STATE_LOWSTATE_TOPIC: str = Field(default="/lowstate")
    STATE_LOWSTATE_MIN_UPDATE_INTERVAL_SEC: float = Field(default=120.0)
    STATE_NETWORK_INTERFACE: str = Field(default="eth0")
    CAMERA_FPS: int = Field(default=30)
    DEPTH_CAMERA_FPS: int = Field(default=6)
    DEPTH_CAMERA_DESCRIPTION_MAX_CONCURRENCY: int = Field(
        default=2,
        description=(
            "Max concurrent depth camera requests when need_description=true. "
            "Helps limit CPU and thread pool pressure from detection + depth post-processing."
        ),
    )
    LOCAL_CAMERA_DEVICE_ID: str | None = Field(
        default=None, description="Additional camera device ID"
    )
    DEFAULT_REMOTE_DETECTOR_URL: str = Field(
        default="http://192.168.2.179:8000/api/dl/yoloworld"
    )
    DL_API_KEY: str = Field(default="", description="API key for DL backend")

    SPEAKER_TTS_ENGINE: str = Field(
        default="openai", description="TTS engine: openai or piper"
    )
    SPEAKER_DEVICE_ID: int | str | None = Field(
        default=None, description="Audio output device ID"
    )
    SPEAKER_SAMPLE_RATE: int = Field(default=48000)
    SPEAKER_BLOCK_SIZE: int = Field(default=1024)
    SPEAKER_CHANNELS: int = Field(default=1)
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key for TTS")
    OPENAI_BASE_URL: str | None = Field(default=None, description="OpenAI API base URL")
    TTS_MODEL: str = Field(default="gpt-4o-mini-tts", description="OpenAI TTS model")
    TTS_VOICE: str = Field(default="coral", description="OpenAI TTS voice")
    DEFAULT_PIPER_MODEL: str = Field(
        default="en_US-lessac-medium.onnx", description="Piper TTS model path"
    )
    SPEAKER_AUDIO_DIR: str = Field(
        default="resources/sound/dog",
        description="Directory containing pre-recorded audio files",
    )
    SPEAKER_CHUNK_WRITE_TIMEOUT: float = Field(
        default=10.0, description="Max seconds to wait for a single audio chunk write"
    )
    SPEAKER_LOCK_ACQUIRE_TIMEOUT: float = Field(
        default=5.0, description="Max seconds to wait for speaker lock"
    )
    SPEAKER_VOLUME: float = Field(
        default=1.0, description="Master volume multiplier (0.0-2.0)"
    )
    SPEAKER_MIXER_VOLUME: int = Field(
        default=100,
        description="ALSA mixer volume percentage (0-100). Set on speaker init via amixer",
    )
    SPEAKER_FADE_IN_MS: int = Field(
        default=0,
        description="Fade-in duration in ms for first audio chunk. Prevents power spike on weak supplies",
    )
    SPEAKER_STARTUP_DELAY_MS: int = Field(
        default=0,
        description="Delay in ms before first audio write after stream start. Gives device time to stabilize",
    )

    SPEAKER_VOLUME_RATE: float = Field(
        default=3.0, description="TTS audio amplification before resampling"
    )
    TTS_SPEED: float = Field(default=1.5, description="OpenAI TTS speech speed")
    TTS_CHUNK_SIZE: int = Field(
        default=2048, description="PCM streaming chunk size in bytes"
    )

    AUDIO_CAPTURE_DEVICE_ID: int | str | None = Field(
        default=None, description="Microphone device ID for audio capture"
    )
    from pydantic import Field, field_validator

    AUDIO_CAPTURE_HOTWORDS: list[str] = Field(
        default=["hello"], description="List of hotword(s) to trigger listening"
    )

    AUDIO_CAPTURE_PATIENCE: int = Field(
        default=3, description="Seconds of silence before ending a command session"
    )
    VOSK_MODEL_ID: str = Field(
        default="vosk-model-small-en-us-0.15", description="Vosk ASR model name"
    )
    DEEPGRAM_MODEL_ID: str = Field(
        default="flux-general-en", description="Deepgram model name"
    )
    AUDIO_CAPTURE_SAMPLE_RATE: int = Field(
        default=16000, description="Microphone sample rate in Hz"
    )
    AUDIO_CAPTURE_CHANNELS: int = Field(
        default=1, description="Microphone channel count"
    )
    AUDIO_CAPTURE_ENGINE: str = Field(
        default="vosk", description="Audio capture ASR engine: vosk or deepgram"
    )
    AUDIO_CAPTURE_SILENCE_THRESHOLD: float = Field(
        default=0.01, description="RMS silence threshold, normalized [-1,1]"
    )
    AUDIO_CAPTURE_CLIENT_DENOISE: bool = Field(
        default=False,
        description="Enable client-side noise reduction (scipy FFT). When False, relies on Deepgram server-side noise handling",
    )
    DEEPGRAM_API_KEY: str = Field(default="", description="Deepgram API key for STT")
    AUDIO_TRANSCRIBE_MAX_CONCURRENCY: int = Field(
        default=2,
        description=(
            "Max concurrent audio transcribe requests. "
            "Helps prevent unbounded executor thread growth during decode/ASR/network calls."
        ),
    )

    DEVICE_WATCHER_ENABLED: bool = Field(
        default=True, description="Enable device watcher for auto-recovery"
    )
    DEVICE_WATCHER_POLL_INTERVAL: float = Field(
        default=5.0, description="Seconds between health checks"
    )
    DEVICE_WATCHER_BASE_BACKOFF: float = Field(
        default=2.0, description="Base backoff in seconds for retry delay"
    )
    DEVICE_WATCHER_MAX_BACKOFF: float = Field(
        default=120.0, description="Max backoff cap in seconds"
    )
    DEVICE_WATCHER_MAX_RETRIES: int = Field(
        default=5, description="Max restart attempts per service (0=unlimited)"
    )
    DEVICE_WATCHER_INITIAL_GRACE_PERIOD: float = Field(
        default=10.0, description="Seconds to wait before first health check"
    )

    @field_validator("AUDIO_CAPTURE_HOTWORDS", mode="before")
    @classmethod
    def parse_hotwords(cls, v: str | list[str]) -> list[str]:
        print(f"[In parse_hotwords] v: {v} ({type(v)})")
        if isinstance(v, str):
            return [hw.strip() for hw in v.split(",") if hw.strip()]
        return v
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=[
            str(Path(__file__).resolve().parent.parent.parent / ".env"),
            ".env",
        ],
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Go2MiddleLayerContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    # --- Lazy factories: modules are imported only when the singleton is first accessed ---

    sport_service = providers.Singleton(
        _lazy_class(
            "impl.sdk_sport.sdk_sport_service",
            "SdkSportService",
            fallback=("impl.sdk_sport.sdk_sport_service_stub", "SdkSportServiceStub"),
        ),
        network_interface=config.state.network_interface,
    )

    # state_service_using_echo = providers.Singleton(
    #     _lazy_class("impl.state.echo_state_service", "Ros2EchoSportStateService"),
    #     sport_topic=config.state.topic,
    #     lowstate_topic=config.state.lowstate_topic,
    #     lowstate_min_update_interval_sec=config.state.lowstate_min_update_interval_sec,
    # )

    state_service_using_ros2 = providers.Singleton(
        _lazy_class(
            "impl.state.ros2_state_service",
            "Ros2SportStateService",
            fallback=(
                "impl.state.ros2_state_service_stub",
                "Ros2SportStateServiceStub",
            ),
        ),
        sport_topic=config.state.topic,
        lowstate_topic=config.state.lowstate_topic,
        lowstate_min_update_interval_sec=config.state.lowstate_min_update_interval_sec,
    )

    rpc_camera_service = providers.Singleton(
        _lazy_class(
            "impl.rpc_camera.rpc_camera_service",
            "RpcCameraService",
            fallback=(
                "impl.rpc_camera.rpc_camera_service_stub",
                "RpcCameraServiceStub",
            ),
        ),
        network_interface=config.state.network_interface,
    )

    depth_camera_service = providers.Singleton(
        _lazy_class(
            "impl.depth_camera.depth_camera_service",
            "DepthCameraService",
            fallback=(
                "impl.depth_camera.depth_camera_service_stub",
                "DepthCameraServiceStub",
            ),
        ),
        config=config.depth_camera,
    )

    local_camera_service = providers.Singleton(
        _lazy_class("impl.local_camera.local_camera_service", "LocalCameraService"),
        device_id=config.local_camera.device_id,
    )

    speaker_service_openai = providers.Singleton(
        _lazy_class("impl.speaker.openai_speaker_service", "OpenAISpeakerService"),
        device_id=config.speaker.device_id,
        sample_rate=config.speaker.sample_rate,
        block_size=config.speaker.block_size,
        channels=config.speaker.channels,
        api_key=config.speaker.openai_api_key,
        base_url=config.speaker.openai_base_url,
        tts_model=config.speaker.tts_model,
        tts_voice=config.speaker.tts_voice,
        volume_rate=config.speaker.volume_rate,
        chunk_write_timeout=config.speaker.chunk_write_timeout,
        lock_acquire_timeout=config.speaker.lock_acquire_timeout,
        tts_speed=config.speaker.tts_speed,
        tts_chunk_size=config.speaker.tts_chunk_size,
        volume=config.speaker.volume,
        fade_in_ms=config.speaker.fade_in_ms,
        startup_delay_ms=config.speaker.startup_delay_ms,
        mixer_volume=config.speaker.mixer_volume,
    )

    speaker_service_piper = providers.Singleton(
        _lazy_class("impl.speaker.piper_speaker_service", "PiperSpeakerService"),
        device_id=config.speaker.device_id,
        sample_rate=config.speaker.sample_rate,
        block_size=config.speaker.block_size,
        channels=config.speaker.channels,
        piper_model=config.speaker.piper_model,
        volume=config.speaker.volume,
        fade_in_ms=config.speaker.fade_in_ms,
        startup_delay_ms=config.speaker.startup_delay_ms,
        mixer_volume=config.speaker.mixer_volume,
    )

    speaker_service = providers.Selector(
        config.speaker.tts_engine,
        openai=speaker_service_openai,
        piper=speaker_service_piper,
    )

    device_watcher_service = providers.Singleton(
        _lazy_class(
            "impl.device_watcher.device_watcher_service", "DeviceWatcherService"
        ),
        poll_interval=config.device_watcher.poll_interval,
        base_backoff=config.device_watcher.base_backoff,
        max_backoff=config.device_watcher.max_backoff,
        max_retries=config.device_watcher.max_retries,
        initial_grace_period=config.device_watcher.initial_grace_period,
    )

    audio_capture_service_vosk = providers.Singleton(
        _lazy_class("impl.audio_capture.stt.vosk", "VoskAudioCaptureService"),
        device_id=config.audio_capture.device_id,
        hotwords=config.audio_capture.hotwords,
        patience=config.audio_capture.patience,
        model_id=config.audio_capture.vosk_model_id,
        sample_rate=config.audio_capture.sample_rate,
        channels=config.audio_capture.channels,
        silence_threshold=config.audio_capture.silence_threshold,
    )

    audio_capture_service_deepgram = providers.Singleton(
        _lazy_class("impl.audio_capture.stt.deepgram", "DeepgramAudioCaptureService"),
        device_id=config.audio_capture.device_id,
        hotwords=config.audio_capture.hotwords,
        patience=config.audio_capture.patience,
        api_key=config.audio_capture.deepgram_api_key,
        model=config.audio_capture.deepgram_model_id,
        sample_rate=config.audio_capture.sample_rate,
        channels=config.audio_capture.channels,
        client_denoise=config.audio_capture.client_denoise,
    )

    audio_capture_service = providers.Selector(
        config.audio_capture.engine,
        vosk=audio_capture_service_vosk,
        deepgram=audio_capture_service_deepgram,
    )


_container = None


def init_container() -> Go2MiddleLayerContainer:
    global _container
    if _container:
        return _container

    settings = ServiceSettings()
    container = Go2MiddleLayerContainer()
    # Resolve relative paths to src/ so they work when run from project root
    audio_dir = str(resolve_src_path(settings.SPEAKER_AUDIO_DIR))
    container.config.from_dict(
        {
            "state": {
                "mode": settings.STATE_SERVICE_MODE,
                "topic": settings.STATE_TOPIC,
                "lowstate_topic": settings.STATE_LOWSTATE_TOPIC,
                "lowstate_min_update_interval_sec": settings.STATE_LOWSTATE_MIN_UPDATE_INTERVAL_SEC,
                "network_interface": settings.STATE_NETWORK_INTERFACE,
            },
            "rpc_camera": {"fps": settings.CAMERA_FPS},
            "depth_camera": {
                "fps": settings.DEPTH_CAMERA_FPS,
                "remote_detector_url": settings.DEFAULT_REMOTE_DETECTOR_URL,
                "dl_api_key": settings.DL_API_KEY,
                "description_max_concurrency": settings.DEPTH_CAMERA_DESCRIPTION_MAX_CONCURRENCY,
            },
            "local_camera": {"device_id": settings.LOCAL_CAMERA_DEVICE_ID},
            "speaker": {
                "tts_engine": settings.SPEAKER_TTS_ENGINE,
                "device_id": settings.SPEAKER_DEVICE_ID,
                "sample_rate": settings.SPEAKER_SAMPLE_RATE,
                "block_size": settings.SPEAKER_BLOCK_SIZE,
                "channels": settings.SPEAKER_CHANNELS,
                "openai_api_key": settings.OPENAI_API_KEY,
                "openai_base_url": settings.OPENAI_BASE_URL,
                "tts_model": settings.TTS_MODEL,
                "tts_voice": settings.TTS_VOICE,
                "piper_model": settings.DEFAULT_PIPER_MODEL,
                "audio_dir": audio_dir,
                "chunk_write_timeout": settings.SPEAKER_CHUNK_WRITE_TIMEOUT,
                "lock_acquire_timeout": settings.SPEAKER_LOCK_ACQUIRE_TIMEOUT,
                "volume": settings.SPEAKER_VOLUME,
                "mixer_volume": settings.SPEAKER_MIXER_VOLUME,
                "volume_rate": settings.SPEAKER_VOLUME_RATE,
                "fade_in_ms": settings.SPEAKER_FADE_IN_MS,
                "startup_delay_ms": settings.SPEAKER_STARTUP_DELAY_MS,
                "tts_speed": settings.TTS_SPEED,
                "tts_chunk_size": settings.TTS_CHUNK_SIZE,
            },
            "device_watcher": {
                "enabled": settings.DEVICE_WATCHER_ENABLED,
                "poll_interval": settings.DEVICE_WATCHER_POLL_INTERVAL,
                "base_backoff": settings.DEVICE_WATCHER_BASE_BACKOFF,
                "max_backoff": settings.DEVICE_WATCHER_MAX_BACKOFF,
                "max_retries": settings.DEVICE_WATCHER_MAX_RETRIES,
                "initial_grace_period": settings.DEVICE_WATCHER_INITIAL_GRACE_PERIOD,
            },
            "audio_capture": {
                "engine": settings.AUDIO_CAPTURE_ENGINE,
                "device_id": settings.AUDIO_CAPTURE_DEVICE_ID,
                "hotwords": settings.AUDIO_CAPTURE_HOTWORDS,
                "patience": settings.AUDIO_CAPTURE_PATIENCE,
                "vosk_model_id": settings.VOSK_MODEL_ID,
                "deepgram_model_id": settings.DEEPGRAM_MODEL_ID,
                "sample_rate": settings.AUDIO_CAPTURE_SAMPLE_RATE,
                "channels": settings.AUDIO_CAPTURE_CHANNELS,
                "silence_threshold": settings.AUDIO_CAPTURE_SILENCE_THRESHOLD,
                "deepgram_api_key": settings.DEEPGRAM_API_KEY,
                "client_denoise": settings.AUDIO_CAPTURE_CLIENT_DENOISE,
                "transcribe_max_concurrency": settings.AUDIO_TRANSCRIBE_MAX_CONCURRENCY,
            },
        }
    )

    _container = container
    return container
