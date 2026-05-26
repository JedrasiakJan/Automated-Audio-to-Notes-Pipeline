# safemed_ai/core/config.py
import os
from dotenv import load_dotenv
from typing import Final, cast

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234/v1")
WHISPER_URL = os.getenv("WHISPER_URL", "http://127.0.0.1:8000/v1/audio/transcriptions")
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

_pepper = os.getenv("APP_PEPPER")
if _pepper is None:
    raise RuntimeError("Brak APP_PEPPER w zmiennych środowiskowych.")
PEPPER: Final[str] = cast(str, _pepper)