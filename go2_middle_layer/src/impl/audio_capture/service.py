"""
Compatibility exports for legacy imports.

The audio capture implementation has been refactored into:
- `impl.audio_capture.stt.vosk.VoskAudioCaptureService`
- `impl.audio_capture.stt.deepgram.DeepgramAudioCaptureService`

New code should import those classes directly.
"""

from impl.audio_capture.stt.deepgram import DeepgramAudioCaptureService
from impl.audio_capture.stt.vosk import VoskAudioCaptureService

# Backwards-compatible names (kept to avoid breaking any external imports).
AudioCaptureServiceImpl = VoskAudioCaptureService
DeepgramAudioCaptureServiceImpl = DeepgramAudioCaptureService

__all__ = [
    "VoskAudioCaptureService",
    "DeepgramAudioCaptureService",
    "AudioCaptureServiceImpl",
    "DeepgramAudioCaptureServiceImpl",
]
