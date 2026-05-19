from __future__ import annotations

import os
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")


def seconds_to_timecode(seconds: float, fps: int = 25) -> str:
    total_frames = int(round(max(0.0, seconds) * fps))
    frames_per_hour = 3600 * fps
    frames_per_minute = 60 * fps

    hours = total_frames // frames_per_hour
    total_frames %= frames_per_hour

    minutes = total_frames // frames_per_minute
    total_frames %= frames_per_minute

    secs = total_frames // fps
    frames = total_frames % fps

    return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"


def densify_sparse_buffers(module: Any) -> None:
    import torch

    for key, buf in list(module._buffers.items()):
        if torch.is_tensor(buf) and getattr(buf, "is_sparse", False):
            module._buffers[key] = buf.to_dense()
    for child in module.children():
        densify_sparse_buffers(child)


def pick_preferred_device() -> str:
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load_whisper_model_robust(model_name: str, preferred_device: str) -> tuple[Any, str]:
    import whisper

    model = whisper.load_model(model_name, device="cpu")
    densify_sparse_buffers(model)

    if preferred_device == "mps":
        try:
            model = model.to("mps")
            return model, "mps"
        except NotImplementedError:
            return model, "cpu"

    if preferred_device == "cuda":
        try:
            model = model.to("cuda")
            return model, "cuda"
        except Exception:
            return model, "cpu"

    return model, "cpu"


class WhisperTranscriber:
    def __init__(self, model_name: str, language: str | None = None) -> None:
        self.model_name = model_name
        self.language = language
        self._model: Any | None = None
        self.device = "unknown"

    def _load(self) -> None:
        if self._model is not None:
            return

        import torch

        preferred = pick_preferred_device()
        self._model, self.device = load_whisper_model_robust(self.model_name, preferred)
        if self.device == "cpu":
            try:
                torch.set_num_threads(max(1, os.cpu_count() or 1))
            except Exception:
                pass

    def transcribe(self, audio_path: Path) -> tuple[dict[str, Any], str, str]:
        self._load()
        options: dict[str, Any] = {
            "verbose": False,
            "fp16": False,
            "beam_size": 1,
            "best_of": 1,
            "temperature": 0,
            "condition_on_previous_text": False,
        }
        if self.language:
            options["language"] = self.language

        result = self._model.transcribe(str(audio_path), **options)
        detected_language = (result.get("language") or self.language or "unknown").strip()
        return result, detected_language, self.device
