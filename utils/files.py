# utils/files.py
import streamlit as st
from services.whisper_service import safe_remove

def cleanup_temp_file() -> None:
    tmp = st.session_state.get("temp_filename")
    safe_remove(tmp)
    st.session_state.pop("temp_filename", None)