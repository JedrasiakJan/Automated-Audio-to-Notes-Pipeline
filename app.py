import streamlit as st
import os
import gc
import uuid
import requests
import time
from st_copy_to_clipboard import st_copy_to_clipboard

from core.logging_config import log_audit
from core.session_state import init_session_state
from core.config import BASE_DIR

from db.connection import init_db
from db.users import (
    is_password_strong,
    check_login,
    delete_user,
    change_password,
    get_all_users,
)
from db.visits import (
    cleanup_old_visits,
    get_today_visits_for_user,
    save_visit,
)
from services.fhir_service import generate_fhir_json
from services.medical_validation import load_leki_list, validate_medical_text
from services.llm_service import get_client, clear_vram, get_global_lock
from services.whisper_service import (
    safe_remove,
    save_uploaded_file,
    submit_audio_for_transcription,
    get_transcription_status,
)
from utils.files import cleanup_temp_file

# WAŻNE: st.set_page_config zawsze musi być pierwszą komendą Streamlit w pliku!
st.set_page_config(page_title="SafeMed AI", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")

# Ukrywamy brzydkie elementy domyślne Streamlita (Menu, Footer, Header)
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            /* Drobne poprawki dla lepszego wyglądu przycisków w sidebarze */
            [data-testid="stSidebar"] [data-testid="baseButton-secondary"] {
                border-color: transparent;
                background-color: rgba(255, 255, 255, 0.05);
            }
            [data-testid="stSidebar"] [data-testid="baseButton-secondary"]:hover {
                background-color: rgba(255, 75, 75, 0.1);
                color: #ff4b4b;
            }
            </style>
            """

st.markdown(hide_streamlit_style, unsafe_allow_html=True)
init_session_state()


# Ustawia FFmpeg względem tego folderu
ffmpeg_path = BASE_DIR
os.environ["PATH"] += os.pathsep + ffmpeg_path
client = get_client()
global_model_lock = get_global_lock()

# Wywołujemy funkcję
init_db()

cleanup_old_visits(1) 

LEKI_DATABASE = load_leki_list()

if not st.session_state['logged_in']:
    st.title("🔒 SafeMed AI - Panel Personelu")
    st.write("Wprowadź dane dostępowe, aby kontynuować.")
    
    with st.form("login_form"):
        username = st.text_input("Login")
        password = st.text_input("Hasło", type="password")
        submitted = st.form_submit_button("Zaloguj się")
        
        if submitted:
            #check_login zwraca dwa parametry: dane usera i status/komunikat
            user_data, status_msg = check_login(username, password)
            
            if user_data:
                st.session_state['logged_in'] = True
                st.session_state['user_id'] = user_data[0]
                st.session_state['user_name'] = user_data[1]
                st.session_state['user_login'] = username
                log_audit("USER_LOGIN", "SUCCESS", "N/A", mode=f"User: {username}")
                st.rerun()
            else:
                # Tutaj wyświetli się np. "Pozostało prób: 2" lub wiadomość o blokadzie
                st.error(status_msg)
                log_audit("USER_LOGIN", "FAILED", "N/A", mode=f"Attempt: {username} | Msg: {status_msg}")
    
    
    # st.stop() zatrzymuje ładowanie reszty aplikacji, dopóki ktoś się nie zaloguje!
    st.stop()
    

MODES = {
    "Medyczny (SOAP)": {
        "icon": "🩺",
        "prompt": """Jako polski asystent medyczny AI, stwórz profesjonalną notatkę SOAP.
                WYŁĄCZNIE W JĘZYKU POLSKIM.
                1. S (Wywiad): Objawy, historia.
                2. O (Badanie): Ciśnienie, tętno, obserwacje.
                3. A (Rozpoznanie): Diagnoza.
                4. P (Plan): Leki, dawkowanie, zalecenia.
                Wypisz osobno LISTĘ LEKÓW i PROSTE ZALECENIA.

                ZASADA KRYTYCZNA: Jeśli w tekście transkrypcji znajdziesz nazwę leku, 
                która brzmi nielogicznie, jest urwana lub nie pasuje do kontekstu schorzenia, 
                zapisz ją jako [? NAZWA] i dodaj ostrzeżenie. 
                LEPIEJ NAPISAĆ [?], NIŻ PODAĆ BŁĘDNĄ NAZWĘ.

                INSTRUKCJA FILTRACJI:
            1. ZIGNORUJ CAŁKOWICIE: 'small talk', rozmowy o pogodzie, polityce, sporcie, dygresje towarzyskie.
                ZASADA BEZPIECZEŃSTWA: Jeśli informacja nie ma znaczenia diagnostycznego lub terapeutycznego, usuń ją. 
            Finalna notatka SOAP musi być czysta, konkretna i profesjonalna.
            Na samym końcu dokumentu, po separatorze '###', wypisz po przecinku wyłącznie nazwy własne leków, które pojawiły się w tekście. Przykład: ### Acard, Bisocard, Furosemid
            """
    },
    "Notariusz (Protokół)": {
        "icon": "📜",
        "prompt": """Jako asystent notarialny AI, przygotuj szkic protokołu.
                1. DATA I MIEJSCE: Wyciągnij z tekstu.
                2. UCZESTNICY: Imiona, nazwiska, role.
                3. DANE FORMALNE: Numery KW, PESEL, kwoty, numery działek.
                4. OŚWIADCZENIA: Kluczowe deklaracje woli (np. rygor 777 kpc).
                Jeśli brakuje danych, zostaw puste miejsce: [__________]."""
    },
    "Prawnik (Analiza)": {
        "icon": "⚖️",
        "prompt": """Jako analityk prawny, przeanalizuj transkrypcję.
                1. FAKTY: Kluczowe wydarzenia chronologicznie.
                2. SPRZECZNOŚCI: Znajdź niespójności w wypowiedziach.
                3. DOWODY: Wskaż potencjalne dowody wymienione w rozmowie.
                4. CYTATY: Najważniejsze fragmenty wypowiedzi."""
    }
}

st.markdown("""
<div style="text-align: center; margin-top: -20px; padding-bottom: 30px;">
    <h1 style="font-size: 3.5rem; font-weight: 800; margin-bottom: 0; letter-spacing: -1px;">
        🛡️ SafeMed <span style="color: #4ade80;">AI</span>
    </h1>
    <p style="font-size: 1.2rem; color: #a0c8a8; margin-top: 5px; font-weight: 400;">
        Lokalny asystent do bezpiecznej analizy i generowania dokumentacji
    </p>
</div>
""", unsafe_allow_html=True)
# ==========================================
# --- HISTORIA DZISIEJSZYCH WIZYT (SIDEBAR) ---
# ==========================================
st.sidebar.markdown(f"""
<div style="
    background: linear-gradient(135deg, #2f4f3e, #3c5f4a);
    padding: 16px 18px;
    border-radius: 14px;
    border: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 10px;
">
    <div style="font-size: 13px; color: #b7d9bf;">👨‍⚕️ Aktywna sesja</div>
    <div style="font-size: 22px; font-weight: 700; color: white; margin-top: 4px;">
        {st.session_state['user_name']}
    </div>
    <div style="font-size: 13px; color: #cfe8d4; margin-top: 6px;">
        Login: {st.session_state.get('user_login', '-')}
    </div>
</div>
""", unsafe_allow_html=True)
# --- PRZYCISKI AKCJI ---
if st.sidebar.button("🚪 Wyloguj się", use_container_width=True):
    log_audit("USER_LOGOUT", "SUCCESS", "N/A", mode=f"User: {st.session_state['user_name']}")
    cleanup_temp_file()
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = None
    st.session_state['user_name'] = ""
    st.session_state['user_login'] = ""
    st.session_state['note_content'] = None
    st.session_state.pop("current_session", None)
    st.session_state.pop("selected_mode", None)
    st.session_state.pop("whisper_task_id", None)
    st.rerun()

# --- KONTO ---
with st.sidebar.expander("👤 Twoje Konto"):
    with st.form("change_password_form"):
        st.markdown("**🔒 Zmień hasło**")
        st_old = st.text_input("Stare hasło", type="password")
        st_new = st.text_input("Nowe hasło", type="password")
        st_confirm = st.text_input("Powtórz nowe hasło", type="password")
        btn_change = st.form_submit_button("Aktualizuj hasło", use_container_width=True)

        if btn_change:
            if st_new != st_confirm:
                st.error("Nowe hasła nie są identyczne!")
            else:
                current_login = st.session_state.get("user_login")
                if not current_login:
                    st.error("❌ Brak aktywnego loginu w sesji.")
                else:
                    user_data, status = check_login(current_login, st_old)
                    if user_data:
                        is_ok, msg = is_password_strong(st_new)
                        if is_ok:
                            try:
                                changed = change_password(st.session_state["user_id"], st_new)
                                if changed:
                                    st.success("✅ Hasło zmienione!")
                                    log_audit("PASSWORD_CHANGE", "SUCCESS", "N/A")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("❌ Nie znaleziono użytkownika.")
                            except Exception as e:
                                st.error(f"Błąd bazy: {e}")
                        else:
                            st.error(msg)
                    else:
                        st.error("❌ Stare hasło jest błędne.")


# ==========================================
# --- PANEL ADMINISTRATORA ---
# ==========================================
if st.session_state['user_name'] == 'Administrator Systemu':
    st.sidebar.divider()
    st.sidebar.markdown("### 👑 Panel Szefa")
    with st.sidebar.expander("👥 Zarządzaj Personelem"):
        try:
            personel = get_all_users()

            if personel:
                for p in personel:
                    u_id, u_login, u_name = p
                    col_dane, col_kosz = st.columns([4, 1])
                    with col_dane:
                        st.markdown(f"**{u_name}**")
                        st.caption(f"🔑 {u_login} · ID: {u_id}")
                    with col_kosz:
                        if u_id != 1:
                            if st.button("🗑️", key=f"del_{u_id}"):
                                sukces, wiadomosc = delete_user(u_id)
                                if sukces:
                                    st.toast(f"✅ {wiadomosc}")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(wiadomosc)
                    st.divider()
                    
            else:
                st.write("Baza jest pusta.")
        except Exception as e:
            st.sidebar.error(f"Błąd panelu: {e}")

# ==========================================
# --- HISTORIA WIZYT ---
# ==========================================
st.sidebar.divider()
st.sidebar.markdown("### 🕒 Twoje dzisiejsze wizyty")

try:
    historia = get_today_visits_for_user(st.session_state["user_id"])
    if not historia:
        st.sidebar.info("Brak notatek z dzisiaj.")
    else:
        for row in historia:
            wizyta_id = row[0][:8]
            godzina = row[1].split()[1][:5]
            ikona = "🩺" if "SOAP" in row[2] else ("📜" if "Notariusz" in row[2] else "⚖️")
            with st.sidebar.expander(f"{ikona} Wizyta {godzina}"):
                st.caption(f"Tryb: {row[2]} · ID: {wizyta_id}")
                st.markdown(f"*{row[3][:80]}...*")
                if st.button("🔄 Przywróć tę wizytę", key=f"btn_restore_{row[0]}", use_container_width=True):
                    st.session_state["note_content"] = row[3]
                    st.session_state["current_session"] = row[0]
                    st.rerun()
except Exception:
    st.sidebar.error("Błąd ładowania historii wizyt.")
# ==========================================
selected_mode = st.selectbox(
    "Wybierz profil asystenta:",
    options=list(MODES.keys()),
    format_func=lambda x: f"{MODES[x]['icon']} {x}"
)

uploaded_file = st.file_uploader("Wgraj nagranie", type=["mp3", "wav", "m4a", "mp4"])

if uploaded_file and st.button("Generuj dokumentację"):
    session_id = str(uuid.uuid4())
    st.session_state["current_session"] = session_id
    st.session_state["selected_mode"] = selected_mode
    temp_filename = None

    try:
        with st.spinner("📤 Wysyłanie nagrania do serwera transkrypcji..."):
            temp_filename = save_uploaded_file(uploaded_file, suffix=".wav")
            task_id = submit_audio_for_transcription(temp_filename)

        st.session_state["whisper_task_id"] = task_id
        st.session_state["temp_filename"] = temp_filename
        st.rerun()

    except Exception as e:
        st.error(f"❌ Błąd zapisu pliku lub połączenia: {e}")
    finally:
        if "whisper_task_id" not in st.session_state:
            safe_remove(temp_filename)

# ==========================================
# --- SYSTEM ODPYTYWANIA (POLLING) Z ST.FRAGMENT ---
# ==========================================

if st.session_state.get('whisper_task_id'):
    st.divider()
    
    # Uruchamiamy ten fragment automatycznie co 2 sekundy bez przeładowywania reszty aplikacji
    @st.fragment(run_every=2)
    def check_whisper_status():
        task_id = st.session_state["whisper_task_id"]
        current_session = st.session_state.get("current_session", "N/A")

        try:
            data = get_transcription_status(task_id)

            if data["status"] in ["pending", "processing"]:
                with st.status("⏳ Krok 1/2: Serwer Whisper przetwarza dźwięk...", expanded=True):
                    st.write("Czekam na zakończenie transkrypcji...")

            elif data["status"] == "completed":
                st.success("✅ Transkrypcja gotowa!")
                raw_text = data["result"]

                st.info(f"🧠 Krok 2/2: Analiza LLM w trybie {st.session_state['selected_mode']}...")

                with global_model_lock:
                    clear_vram()
                    l_start = time.time()
                    try:
                        instruction = MODES[st.session_state["selected_mode"]]["prompt"]
                        final_prompt = f"{instruction}\n\nTekst do analizy:\n{raw_text}"

                        chat_completion = client.chat.completions.create(
                            model="local-model",
                            messages=[{"role": "user", "content": final_prompt}],
                            temperature=0.1,
                            max_tokens=-1,
                            timeout=900.0
                        )
                        l_duration = round(time.time() - l_start, 2)

                        full_response = chat_completion.choices[0].message.content or ""
                        log_audit("LLM_ANALYSIS", "SUCCESS", current_session, duration=l_duration)

                        if "</thought>" in full_response:
                            clean_response = full_response.split("</thought>")[-1].strip()
                        elif "thought" in full_response:
                            clean_response = full_response.split("thought")[-1].strip().lstrip(">").strip()
                        else:
                            clean_response = full_response

                        st.session_state["note_content"] = clean_response

                        save_visit(
                            user_id=st.session_state["user_id"],
                            session_id=current_session,
                            typ_notatki=st.session_state["selected_mode"],
                            tresc=clean_response,
                        )

                    except Exception as e:
                        log_audit("CRITICAL_ERROR", str(e), current_session)
                        st.error(f"❌ Błąd modelu LLM: {e}")

                cleanup_temp_file()
                del st.session_state["whisper_task_id"]
                st.rerun()

            elif data["status"] == "failed":
                cleanup_temp_file()
                st.error(f"❌ Błąd serwera Whisper w tle: {data.get('error')}")
                del st.session_state["whisper_task_id"]
                st.stop()

        except requests.exceptions.ConnectionError:
            st.warning("⚠️ Oczekiwanie na odpowiedź serwera Whisper (port 8000)...")

        except requests.exceptions.HTTPError as e:
            cleanup_temp_file()
            st.error(f"❌ Serwer Whisper zwrócił błąd HTTP: {e}")
            st.session_state.pop("whisper_task_id", None)

        except requests.exceptions.RequestException as e:
            st.warning(f"⚠️ Problem z połączeniem z serwerem Whisper: {e}")

    # Uruchamiamy fragment
    check_whisper_status()

# 5. WYŚWIETLANIE WYNIKÓW
if st.session_state.get('note_content'):
    st.divider()
    raw_note = st.session_state['note_content']
    
    if selected_mode == "Medyczny (SOAP)":
        with st.spinner("🔍 Weryfikacja leków..."):
            final_display = validate_medical_text(raw_note, LEKI_DATABASE) or raw_note
    else:
        final_display = raw_note

    st.subheader(f"📄 Wynik: {selected_mode}")
    
    if final_display:
        with st.container(border=True):
            st.markdown(final_display)
        if "⚠️" in final_display:
            st.warning("🚨 Niektóre nazwy (oznaczone ⚠️) wymagają Twojej uwagi.")

        # --- PANEL AKCJI (Z ZABEZPIECZENIEM PRAWNYM) ---
        st.divider()
        st.subheader("✅ Zatwierdzenie i Eksport")
        
        # Checkbox, który kontroluje wszystko poniżej
        zatwierdzenie = st.checkbox(
            "Oświadczam, że zweryfikowałem poprawność danych medycznych i zatwierdzam treść notatki.",
            key="audit_checkbox"
        )

        # Tworzymy kolumny
        col_copy, col_fhir = st.columns(2)
        
        with col_copy:
            st.write("📋 **Kopiowanie**")
            if zatwierdzenie:
                # Ten blok kodu wykona się TYLKO gdy checkbox jest zaznaczony
                st_copy_to_clipboard(final_display)
                st.caption("Tekst gotowy do skopiowania.")
            else:
                # Gdy checkbox nie jest zaznaczony, pokazujemy martwy przycisk
                st.button("📋 Kopiuj (Zablokowane)", disabled=True, key="btn_copy_disabled")

        with col_fhir:
            if selected_mode == "Medyczny (SOAP)":
                st.write("🏥 **Eksport FHIR**")
                if zatwierdzenie:
                    # Ten blok kodu wykona się TYLKO gdy checkbox jest zaznaczony
                    fhir_data = generate_fhir_json(raw_note)
                    st.download_button(
                        label="📥 Pobierz FHIR (.json)",
                        data=fhir_data,
                        file_name=f"fhir_soap_{int(time.time())}.json",
                        mime="application/json",
                        key="btn_fhir_active"
                    )
                else:
                    # Gdy checkbox nie jest zaznaczony, pokazujemy martwy przycisk
                    st.button("📥 Pobierz FHIR (Zablokowane)", disabled=True, key="btn_fhir_disabled")

        if not zatwierdzenie:
            st.info("ℹ️ Musisz zaznaczyć oświadczenie powyżej, aby odblokować akcje.")

        # --- PRZYCISK RESETU (Na samym dole) ---
        st.divider()
        if st.button("🗑️ Rozpocznij nową wizytę", use_container_width=True):
            current_id = st.session_state.get("current_session", "N/A")
            cleanup_temp_file()
            st.session_state["note_content"] = None
            st.session_state.pop("current_session", None)
            st.session_state.pop("selected_mode", None)
            st.session_state.pop("whisper_task_id", None)
            st.session_state.pop("audit_checkbox", None)

            with global_model_lock:
                clear_vram()

            gc.collect()
            log_audit("USER_SESSION_RESET", "SUCCESS", current_id)
            st.rerun()
    else:
        st.error("Wystąpił błąd przy wyświetlaniu notatki.")
    

# --- ADRESY DLA MAC STUDIO W SIECI LOKALNEJ ---
# Jeśli Mac ma IP 192.168.1.50, to adresy będą wyglądać tak:
# WHISPER_SERVER_URL = "http://192.168.1.50:8000/v1/audio/transcriptions"
# client = OpenAI(base_url="http://192.168.1.50:1234/v1", api_key="lm-studio")