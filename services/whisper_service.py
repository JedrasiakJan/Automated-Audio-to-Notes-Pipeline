import os
import tempfile
from typing import Any

import requests

from core.config import WHISPER_URL
from core.logging_config import app_logger


def safe_remove(path: str | None) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError as e:
        app_logger.warning(f"Nie udało się usunąć pliku {path}: {e}")


def save_uploaded_file(uploaded_file, suffix: str = ".wav") -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(uploaded_file.getbuffer())
        return tmp_file.name


def submit_audio_for_transcription(temp_filename: str) -> str:
    with open(temp_filename, "rb") as f:
        response = requests.post(
            f"{WHISPER_URL}/async",
            files={"file": f},
            timeout=120,
        )

    response.raise_for_status()
    data = response.json()
    return data["task_id"]


def get_transcription_status(task_id: str) -> dict[str, Any]:
    base_whisper = WHISPER_URL.replace("/transcriptions", "")
    response = requests.get(
        f"{base_whisper}/transcriptions/status/{task_id}",
        timeout=15,
    )
    response.raise_for_status()
    return response.json()