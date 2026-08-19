def __getattr__(name):
    """Lazy re-exports — TTS engines are only imported on first access."""
    if name == "OpenAISpeakerService":
        from impl.speaker.openai_speaker_service import OpenAISpeakerService

        return OpenAISpeakerService
    if name == "PiperSpeakerService":
        from impl.speaker.piper_speaker_service import PiperSpeakerService

        return PiperSpeakerService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["OpenAISpeakerService", "PiperSpeakerService"]
