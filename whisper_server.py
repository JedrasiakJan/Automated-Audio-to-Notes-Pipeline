from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from faster_whisper import WhisperModel
import uvicorn
import os
import uuid
import tempfile
import threading
import time
from typing import Dict, Any


TASK_TTL_SECONDS = 60 * 60
MAX_UPLOAD_SIZE_MB = 200
MODEL_SIZE = "small"
MODEL_DEVICE = "cpu"
MODEL_COMPUTE_TYPE = "int8"


tasks_db: Dict[str, Dict[str, Any]] = {}
tasks_lock = threading.Lock()
model_lock = threading.Lock()
model: WhisperModel | None = None


def now_mono() -> float:
    return time.monotonic()


def cleanup_expired_tasks() -> None:
    cutoff = now_mono() - TASK_TTL_SECONDS
    with tasks_lock:
        expired_ids = [
            task_id
            for task_id, data in tasks_db.items()
            if data.get("created_monotonic", 0) < cutoff
        ]
        for task_id in expired_ids:
            tasks_db.pop(task_id, None)


def set_task(task_id: str, **updates: Any) -> None:
    with tasks_lock:
        if task_id in tasks_db:
            tasks_db[task_id].update(updates)


def create_task_record(task_id: str, filename: str | None) -> None:
    with tasks_lock:
        tasks_db[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "result": None,
            "error": None,
            "filename": filename,
            "created_monotonic": now_mono(),
            "started_monotonic": None,
            "finished_monotonic": None,
        }


def get_task(task_id: str) -> Dict[str, Any] | None:
    with tasks_lock:
        task = tasks_db.get(task_id)
        if task is None:
            return None
        return dict(task)


def safe_remove(path: str | None) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def process_audio_task(task_id: str, temp_path: str) -> None:
    global model

    if model is None:
        set_task(
            task_id,
            status="failed",
            error="Model Whisper nie został załadowany.",
            finished_monotonic=now_mono(),
        )
        safe_remove(temp_path)
        return

    local_model = model

    set_task(task_id, status="processing", started_monotonic=now_mono())

    try:
        with model_lock:
            segments, info = local_model.transcribe(
                temp_path,
                beam_size=5,
                language="pl"
            )

        text = " ".join(segment.text.strip() for segment in segments).strip()

        set_task(
            task_id,
            status="completed",
            result=text,
            error=None,
            finished_monotonic=now_mono(),
            detected_language=getattr(info, "language", "pl"),
            duration_seconds=getattr(info, "duration", None),
        )

    except Exception as e:
        set_task(
            task_id,
            status="failed",
            error=str(e),
            finished_monotonic=now_mono(),
        )

    finally:
        safe_remove(temp_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model

    print("⏳ Ładowanie modelu Whisper...")
    try:
        model = WhisperModel(
            MODEL_SIZE,
            device=MODEL_DEVICE,
            compute_type=MODEL_COMPUTE_TYPE
        )
        print("✅ Model załadowany pomyślnie!")
    except Exception as e:
        print(f"❌ BŁĄD ŁADOWANIA MODELU: {e}")
        raise RuntimeError(f"Nie udało się załadować modelu Whisper: {e}")

    yield

    print("🛑 Zamykanie aplikacji Whisper server...")


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def healthcheck():
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "model_size": MODEL_SIZE,
        "device": MODEL_DEVICE,
    }


@app.post("/v1/audio/transcriptions/async")
async def transcribe_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    cleanup_expired_tasks()

    if model is None:
        raise HTTPException(status_code=503, detail="Model Whisper nie jest gotowy.")

    task_id = str(uuid.uuid4())
    temp_path = None

    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Brak nazwy pliku.")

        suffix = os.path.splitext(file.filename)[1].lower() or ".tmp"

        allowed_suffixes = {".mp3", ".wav", ".m4a", ".mp4", ".mpeg", ".mpga", ".webm"}
        if suffix not in allowed_suffixes:
            raise HTTPException(
                status_code=400,
                detail=f"Nieobsługiwany format pliku: {suffix}"
            )

        max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
        chunk_size = 1024 * 1024  # 1 MB
        total_size = 0

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name

            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break

                total_size += len(chunk)
                if total_size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Plik jest za duży. Limit: {MAX_UPLOAD_SIZE_MB} MB."
                    )

                tmp.write(chunk)

        await file.close()

        create_task_record(task_id, file.filename)
        background_tasks.add_task(process_audio_task, task_id, temp_path)

        return {
            "task_id": task_id,
            "status": "pending",
        }

    except HTTPException:
        safe_remove(temp_path)
        try:
            await file.close()
        except Exception:
            pass
        raise

    except Exception as e:
        safe_remove(temp_path)
        try:
            await file.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Błąd uploadu: {e}")


@app.get("/v1/audio/transcriptions/status/{task_id}")
async def get_task_status(task_id: str):
    cleanup_expired_tasks()

    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Zadanie nie znalezione")

    created = task.pop("created_monotonic", None)
    started = task.pop("started_monotonic", None)
    finished = task.pop("finished_monotonic", None)

    if created is not None:
        task["age_seconds"] = round(now_mono() - created, 2)
    if started is not None and finished is not None:
        task["processing_seconds"] = round(finished - started, 2)
    elif started is not None:
        task["processing_seconds"] = round(now_mono() - started, 2)

    return task


if __name__ == "__main__":
    print("🚀 Startowanie serwera Uvicorn na porcie 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)