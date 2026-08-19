def __getattr__(name):
    """Lazy re-exports — STT engines are only imported on first access."""
    if name == "VoskAudioCaptureService":
        from impl.audio_capture.stt.vosk import VoskAudioCaptureService

        return VoskAudioCaptureService
    if name == "DeepgramAudioCaptureService":
        from impl.audio_capture.stt.deepgram import DeepgramAudioCaptureService

        return DeepgramAudioCaptureService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["VoskAudioCaptureService", "DeepgramAudioCaptureService"]
