# safemed_ai/core/logging_config.py
import logging
import os
from logging.handlers import RotatingFileHandler
import streamlit as st

from core.config import BASE_DIR

LOG_FILE = os.path.join(BASE_DIR, "app.log")

app_logger = logging.getLogger("SafeMedLogger")
app_logger.setLevel(logging.INFO)
app_logger.propagate = False

if app_logger.hasHandlers():
    app_logger.handlers.clear()

log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

my_handler = RotatingFileHandler(
    LOG_FILE,
    mode="a",
    maxBytes=10 * 1024 * 1024,
    backupCount=10,
    encoding="utf-8"
)
my_handler.setFormatter(log_formatter)
app_logger.addHandler(my_handler)

logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

def log_audit(action, status, session_id, mode=None, duration=None):
    user = st.session_state.get("user_name", "GUEST")
    u_id = st.session_state.get("user_id", "N/A")

    entry = f"AUDIT | User: {user} (ID: {u_id}) | Session: {session_id} | ACTION: {action} | STATUS: {status}"

    if mode:
        entry += f" | MODE: {mode}"
    if duration:
        entry += f" | TIME: {duration}s"

    app_logger.info(entry)