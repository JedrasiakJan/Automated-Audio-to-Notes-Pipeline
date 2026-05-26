import csv
import os
import re
from typing import List

from thefuzz import process

from core.config import BASE_DIR
from core.logging_config import app_logger


def load_leki_list() -> List[str]:
    file_path = os.path.join(BASE_DIR, "assets", "leki_pro.csv")

    if not os.path.exists(file_path):
        app_logger.warning(f"Nie znaleziono bazy leków: {file_path}")
        return []

    try:
        with open(file_path, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            return [row[0] for row in reader if row]
    except Exception as e:
        app_logger.error(f"Błąd podczas odczytu bazy leków: {e}")
        return []


def validate_medical_text(text: str, leki_database: list[str]) -> str:
    if not leki_database or not text:
        return text

    meds_raw = ""
    if "###" in text:
        meds_raw = text.split("###")[-1]
    else:
        lines = text.strip().split("\n")
        if lines and "," in lines[-1]:
            meds_raw = lines[-1]

    if not meds_raw:
        return text

    meds_to_check = [m.strip().strip(".,") for m in meds_raw.split(",") if len(m.strip()) > 2]
    validated_text = text

    for med in set(meds_to_check):
        match_tuple = process.extractOne(med.upper(), leki_database)

        if match_tuple:
            score = match_tuple[1]
            pattern = rf"\b{re.escape(med)}\b"

            if score >= 90:
                validated_text = re.sub(pattern, f"✅ {med}", validated_text, flags=re.IGNORECASE)
            else:
                validated_text = re.sub(pattern, f"⚠️ **{med}**", validated_text, flags=re.IGNORECASE)

    return validated_text