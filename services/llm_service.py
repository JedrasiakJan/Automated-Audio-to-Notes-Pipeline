import gc
import threading
import time

import torch
from openai import OpenAI

from core.config import LM_STUDIO_URL


def get_client() -> OpenAI:
    return OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio", timeout=600.0)


def clear_vram() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


_global_model_lock = threading.Lock()


def get_global_lock() -> threading.Lock:
    return _global_model_lock


def extract_clean_response(full_response: str) -> str:
    if "</thought>" in full_response:
        return full_response.split("</thought>")[-1].strip()
    if "thought" in full_response:
        return full_response.split("thought")[-1].strip().lstrip(">").strip()
    return full_response.strip()


def analyze_text(client: OpenAI, instruction: str, raw_text: str) -> tuple[str, float]:
    final_prompt = f"{instruction}\n\nTekst do analizy:\n{raw_text}"
    start = time.time()

    chat_completion = client.chat.completions.create(
        model="local-model",
        messages=[{"role": "user", "content": final_prompt}],
        temperature=0.1,
        max_tokens=-1,
        timeout=900.0,
    )

    duration = round(time.time() - start, 2)
    full_response = chat_completion.choices[0].message.content or ""
    clean_response = extract_clean_response(full_response)

    return clean_response, duration