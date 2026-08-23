"""Smoke test script to verify real AI models inference on local hardware."""

import argparse
import struct
import sys
import wave
from pathlib import Path

# Add backend directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import torch

from app.services.ai import (
    AIServiceError,
    QwenContextAnalyzer,
    TextModerationSignal,
    TimestampedFrame,
    TranscriptSegment,
    TransformerTextModerator,
    VisualDetection,
    WhisperTranscriber,
    YoloVisionAnalyzer,
)
from app.services.video.processing import AudioArtifact


def check_environment() -> None:
    print("--------------------------------------------------")
    print("Environment & Hardware Diagnostics:")
    print(f"  Python version: {sys.version}")
    print(f"  PyTorch version: {torch.__version__}")
    cuda_available = torch.cuda.is_available()
    print(f"  CUDA available: {cuda_available}")
    if cuda_available:
        print(f"  Device count: {torch.cuda.device_count()}")
        print(f"  Device 0: {torch.cuda.get_device_name(0)}")
        print(f"  CUDA capability: {torch.cuda.get_device_capability(0)}")
    print("--------------------------------------------------")


def test_real_vision(device: str = "cpu") -> bool:
    print(f"\n[1/4] Testing YoloVisionAnalyzer (model=yolov8n.pt, device={device})...")
    analyzer = YoloVisionAnalyzer(model_name_or_path="yolov8n.pt", device=device, confidence_threshold=0.25)

    # Create temporary dummy test frame with a simple drawn rectangle
    import cv2
    import numpy as np

    temp_frame = root_dir / "storage" / "smoke_test_frame.jpg"
    temp_frame.parent.mkdir(parents=True, exist_ok=True)
    img = np.zeros((320, 320, 3), dtype=np.uint8)
    cv2.rectangle(img, (50, 50), (200, 200), (255, 255, 255), -1)
    cv2.imwrite(str(temp_frame), img)

    try:
        frame = TimestampedFrame("smoke_frame", 0.0, str(temp_frame))
        detections = analyzer.analyze([frame])
        print(f"  -> SUCCESS: YOLO model loaded and inference ran successfully.")
        print(f"  -> Detected objects count: {len(detections)}")
        for det in detections:
            print(f"     * Category: {det.category}, Confidence: {det.confidence:.2f}, Box: {det.metadata.get('box')}")
        return True
    except Exception as exc:
        print(f"  -> FAILURE in YoloVisionAnalyzer: {exc}")
        return False
    finally:
        temp_frame.unlink(missing_ok=True)


def test_real_text_moderation(device: str = "cpu") -> bool:
    print(f"\n[2/4] Testing TransformerTextModerator (model=unitary/toxic-bert, device={device})...")
    moderator = TransformerTextModerator(
        model_name="unitary/toxic-bert",
        device=device,
        confidence_threshold=0.5,
    )
    segments = [
        TranscriptSegment(0.0, 2.0, "Hello, welcome to our cooking class."),
        TranscriptSegment(2.5, 5.0, "I will attack you and hurt you!"),
    ]
    try:
        signals = moderator.moderate(segments)
        print(f"  -> SUCCESS: Transformer model loaded and inference ran successfully.")
        print(f"  -> Extracted policy signals count: {len(signals)}")
        for sig in signals:
            print(
                f"     * [{sig.start_timestamp}s - {sig.end_timestamp}s] Category: {sig.category}, Confidence: {sig.confidence:.2f}, Text: '{sig.source_text}'"
            )
        return True
    except Exception as exc:
        print(f"  -> FAILURE in TransformerTextModerator: {exc}")
        return False


def test_real_transcription(device: str = "cpu") -> bool:
    print(f"\n[3/4] Testing WhisperTranscriber (model=tiny, device={device})...")
    transcriber = WhisperTranscriber(model_name="tiny", device=device)

    # 1. Test graceful no-audio handling
    no_audio = AudioArtifact(audio_available=False, storage_path=None, format=None, duration=None)
    empty_segments = transcriber.transcribe(no_audio)
    assert empty_segments == [], "Expected empty segments for no audio"
    print("  -> Graceful no-audio handling verified.")

    # 2. Test real audio inference with a synthesized 1-second 16kHz WAV file
    temp_wav = root_dir / "storage" / "smoke_test_audio.wav"
    temp_wav.parent.mkdir(parents=True, exist_ok=True)

    sample_rate = 16000
    duration_s = 1.0
    num_samples = int(sample_rate * duration_s)

    with wave.open(str(temp_wav), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for _ in range(num_samples):
            wav_file.writeframes(struct.pack("<h", 0))

    try:
        audio_artifact = AudioArtifact(audio_available=True, storage_path=temp_wav, format="wav", duration=duration_s)
        segments = transcriber.transcribe(audio_artifact)
        print(f"  -> SUCCESS: Whisper model loaded and audio transcription ran successfully.")
        print(f"  -> Extracted transcript segments count: {len(segments)}")
        for seg in segments:
            print(f"     * [{seg.start}s - {seg.end}s] '{seg.text}'")
        return True
    except Exception as exc:
        print(f"  -> FAILURE in WhisperTranscriber: {exc}")
        return False
    finally:
        temp_wav.unlink(missing_ok=True)


def test_real_context(model_name: str = "qwen2.5vl:7b") -> bool:
    print(f"\n[4/4] Testing QwenContextAnalyzer (model={model_name} via Ollama)...")
    analyzer = QwenContextAnalyzer(model_name=model_name, base_url="http://127.0.0.1:11434")

    # Create dummy culinary frame
    import cv2
    import numpy as np

    temp_frame = root_dir / "storage" / "smoke_test_kitchen.jpg"
    temp_frame.parent.mkdir(parents=True, exist_ok=True)
    img = np.zeros((320, 320, 3), dtype=np.uint8)
    cv2.putText(img, "Kitchen", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.imwrite(str(temp_frame), img)

    try:
        detections = [VisualDetection("knife", 0.92, 1.5, "frame_0001", {"box": "[50, 50, 120, 200]"})]
        transcripts = [TranscriptSegment(0.0, 3.0, "Today we will prepare vegetables for our dish.")]
        signals = [TextModerationSignal("clean", 0.99, 0.0, 3.0, "Today we will prepare vegetables for our dish.")]
        frames = [TimestampedFrame("frame_0001", 1.5, str(temp_frame))]

        interpretation = analyzer.analyze(detections, transcripts, signals, frames)
        print(f"  -> SUCCESS: Qwen multimodal context reasoning ran successfully.")
        print(f"     * Category: {interpretation.category}")
        print(f"     * Confidence: {interpretation.confidence:.2f}")
        print(f"     * Reasoning: {interpretation.reasoning}")
        print(f"     * Evidence References: {interpretation.evidence_references}")
        return True
    except Exception as exc:
        print(f"  -> FAILURE in QwenContextAnalyzer: {exc}")
        return False
    finally:
        temp_frame.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test real AI model adapters.")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="Inference device for PyTorch")
    parser.add_argument("--qwen-model", default="qwen2.5vl:7b", help="Ollama Qwen model tag")
    args = parser.parse_args()

    print("==================================================")
    print(f"SafeScreen AI — Milestone 7 Multimodal Smoke Test")
    print("==================================================")

    check_environment()

    vision_ok = test_real_vision(args.device)
    text_ok = test_real_text_moderation(args.device)
    transcription_ok = test_real_transcription(args.device)
    context_ok = test_real_context(args.qwen_model)

    print("\n==================================================")
    print("Summary of Real Model Smoke Test:")
    print(f"  Device: {args.device.upper()}")
    print(f"  Vision (YOLO): {'PASS' if vision_ok else 'FAIL'}")
    print(f"  Text Moderation (Transformer): {'PASS' if text_ok else 'FAIL'}")
    print(f"  Transcription (Whisper): {'PASS' if transcription_ok else 'FAIL'}")
    print(f"  Context Reasoning (Qwen 2.5 VL): {'PASS' if context_ok else 'FAIL'}")
    print("==================================================")

    if not (vision_ok and text_ok and transcription_ok and context_ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
