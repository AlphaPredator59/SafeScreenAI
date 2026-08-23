"""Whisper-based speech-to-text adapter for timestamped audio transcription."""

from pathlib import Path
from typing import Any

from app.services.ai.contracts import AIServiceError, TranscriptSegment
from app.services.video.processing import AudioArtifact


class WhisperTranscriber:
    """Transcriber adapter using OpenAI Whisper models."""

    def __init__(
        self,
        model_name: str = "tiny",
        device: str = "cpu",
        language: str | None = None,
        model: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.language = language
        self._model = model

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            import whisper

            self._model = whisper.load_model(self.model_name, device=self.device)
            return self._model
        except Exception as error:
            raise AIServiceError(f"Failed to load Whisper model '{self.model_name}': {error}") from error

    @staticmethod
    def _load_audio_waveform(audio_path: Path) -> Any:
        """Load audio into float32 16kHz mono waveform with fallback."""
        if audio_path.suffix.lower() == ".wav":
            try:
                import wave
                import numpy as np

                with wave.open(str(audio_path), "rb") as wf:
                    channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    framerate = wf.getframerate()
                    frames = wf.readframes(wf.getnframes())

                    if sampwidth == 2:
                        data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                    elif sampwidth == 4:
                        data = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
                    else:
                        data = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

                    if channels > 1:
                        data = data.reshape(-1, channels).mean(axis=1)

                    if framerate != 16000 and len(data) > 0:
                        import scipy.signal

                        num_resampled = int(len(data) * 16000 / framerate)
                        data = scipy.signal.resample(data, num_resampled).astype(np.float32)

                    return data
            except Exception:
                pass

        try:
            import whisper

            return whisper.load_audio(str(audio_path))
        except Exception:
            return str(audio_path)

    def transcribe(self, audio: AudioArtifact) -> list[TranscriptSegment]:
        """Transcribe an extracted audio artifact into timestamped segments."""
        if not audio.audio_available or audio.storage_path is None:
            return []

        audio_path = Path(audio.storage_path)
        if not audio_path.exists():
            raise AIServiceError(f"Audio file not found at storage path: {audio.storage_path}")

        model = self._get_model()

        kwargs: dict[str, Any] = {}
        if self.language:
            kwargs["language"] = self.language

        try:
            audio_input = self._load_audio_waveform(audio_path)
            result = model.transcribe(audio_input, **kwargs)
        except Exception as error:
            raise AIServiceError(f"Whisper transcription failed for {audio.storage_path}: {error}") from error

        raw_segments = result.get("segments") if isinstance(result, dict) else None
        if raw_segments is None:
            text = str(result.get("text", "")).strip() if isinstance(result, dict) else ""
            if text:
                duration = audio.duration or 1.0
                return [TranscriptSegment(start=0.0, end=max(duration, 0.0), text=text)]
            return []

        segments: list[TranscriptSegment] = []
        for raw_seg in raw_segments:
            try:
                start = float(raw_seg.get("start", 0.0))
                end = float(raw_seg.get("end", start))
                text = str(raw_seg.get("text", "")).strip()
                if not text:
                    continue
                # Ensure start/end invariant (end >= start >= 0)
                start = max(start, 0.0)
                end = max(end, start)
                segments.append(TranscriptSegment(start=start, end=end, text=text))
            except Exception as error:
                raise AIServiceError(f"Failed to parse Whisper segment: {error}") from error

        return segments
