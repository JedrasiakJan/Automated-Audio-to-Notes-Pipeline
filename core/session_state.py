# safemed_ai/core/session_state.py
import streamlit as st

def init_session_state():
    defaults = {
        "logged_in": False,
        "user_id": None,
        "user_name": "",
        "user_login": "",
        "note_content": None,
        "current_session": None,
        "selected_mode": None,
        "whisper_task_id": None,
        "temp_filename": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value