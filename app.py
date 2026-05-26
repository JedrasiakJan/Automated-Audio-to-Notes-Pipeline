import streamlit as st
from openai import OpenAI
import os
import threading
import re
import csv
import json
import gc
import torch
import uuid
import requests
import time
import logging
import bcrypt
import tempfile
from dotenv import load_dotenv
from thefuzz import process
from st_copy_to_clipboard import st_copy_to_clipboard
from logging.handlers import RotatingFileHandler
import sqlite3
from datetime import datetime, timedelta
from contextlib import closing

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
# Konfiguracja ścieżek i klienta
# Pobiera absolutną ścieżkę do folderu, w którym znajduje się app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ustawia FFmpeg względem tego folderu
ffmpeg_path = BASE_DIR
os.environ["PATH"] += os.pathsep + ffmpeg_path


load_dotenv()
# WAŻNE: Dodajemy /v1 na końcu adresu
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234/v1") # Drugi parametr to fallback
WHISPER_URL = os.getenv("WHISPER_URL", "http://127.0.0.1:8000/v1/audio/transcriptions")

client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio", timeout=600.0)
#client = OpenAI(base_url="http://host.docker.internal:1234/v1", api_key="lm-studio", timeout=600.0)

def clear_vram():
    gc.collect() # Czyści nieużywane obiekty z RAM
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    # 2. Wersja dla docelowego Mac Studio (Apple Silicon / MPS) - zahaszkowana:
    # if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    #     torch.mps.empty_cache()
@st.cache_resource
def get_global_lock():
    return threading.Lock()

global_model_lock = get_global_lock()
# ---  KONFIGURACJA LOGOWANIA (ROTACJA) ---
log_file = 'app.log'
app_logger = logging.getLogger("SafeMedLogger") # Nadajemy mu unikalną nazwę
app_logger.setLevel(logging.INFO)
app_logger.propagate = False # Zapobiega dublowaniu przez logger 'root'

# Czyścimy WSZYSTKIE stare handlery, jeśli jakieś zostały z poprzedniej sesji Streamlit
if app_logger.hasHandlers():
    app_logger.handlers.clear()

# Tworzymy JEDEN nowy handler
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
my_handler = RotatingFileHandler(
    log_file, 
    mode='a', 
    maxBytes=10*1024*1024, 
    backupCount=10, 
    encoding='utf-8'
)
my_handler.setFormatter(log_formatter)
app_logger.addHandler(my_handler)



# Wyciszamy biblioteki systemowe (żeby nie pisały 5 razy tego samego)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

def log_audit(action, status, session_id, mode=None, duration=None):
    """Tworzy ustandaryzowany wpis do logów z automatycznym przypisaniem użytkownika."""
    
    # Próbujemy pobrać nazwę użytkownika, jeśli jest zalogowany
    user = st.session_state.get('user_name', 'GUEST')
    u_id = st.session_state.get('user_id', 'N/A')
    
    entry = f"AUDIT | User: {user} (ID: {u_id}) | Session: {session_id} | ACTION: {action} | STATUS: {status}"
    
    if mode:
        entry += f" | MODE: {mode}"
    if duration:
        entry += f" | TIME: {duration}s"
        
    app_logger.info(entry)
# --- WCZYTYWANIE KONFIGURACJI ---
PEPPER = os.getenv("APP_PEPPER") # Pobieramy pieprz z .env
if not PEPPER:
    raise RuntimeError("Brak APP_PEPPER w zmiennych środowiskowych.")

def safe_remove(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError as e:
        app_logger.warning(f"Nie udało się usunąć pliku {path}: {e}")

def cleanup_temp_file():
    tmp = st.session_state.get("temp_filename")
    safe_remove(tmp)
    st.session_state.pop("temp_filename", None)

def get_db_connection():
    """Centralna funkcja do łączenia z bazą. Zawsze włącza tryb WAL."""
    db_path = os.path.join(BASE_DIR, 'historia_wizyt.db')
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def is_password_strong(password):
    """Sprawdza, czy hasło spełnia standardy bezpieczeństwa (min. 12 znaków, cyfra, duża litera)."""
    if len(password) < 12:
        return False, "Hasło musi mieć co najmniej 12 znaków."
    if not re.search(r"\d", password):
        return False, "Hasło musi zawierać przynajmniej jedną cyfrę."
    if not re.search(r"[A-Z]", password):
        return False, "Hasło musi zawierać przynajmniej jedną wielką literę."
    if not re.search(r"[a-z]", password):
        return False, "Hasło musi zawierać przynajmniej jedną małą literę."
    return True, ""

def create_user(login, plaintext_password, imie_nazwisko):
    """Tworzy użytkownika z solą (bcrypt) i pieprzem (.env)."""
    # Łączymy hasło z pieprzem przed hashowaniem
    haslo_z_pieprzem = (plaintext_password + PEPPER).encode('utf-8')
    
    # bcrypt automatycznie generuje unikalną sól dla każdego wywołania
    hashed_password = bcrypt.hashpw(haslo_z_pieprzem, bcrypt.gensalt(rounds=14))
    
    try:
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            # Sprawdzamy czy login już istnieje, żeby nie dublować
            c.execute("SELECT login FROM uzytkownicy WHERE login=?", (login,))
            if not c.fetchone():
                c.execute("INSERT INTO uzytkownicy (login, password, imie_nazwisko) VALUES (?, ?, ?)", 
                          (login, hashed_password, imie_nazwisko))
                conn.commit()
    except Exception as e:
        app_logger.error(f"Błąd przy tworzeniu użytkownika {login}: {e}")

def check_login(username, provided_password):
    """Weryfikacja hasła z systemem blokady po 5 nieudanych próbach."""
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT id, password, imie_nazwisko, failed_attempts, lock_until FROM uzytkownicy WHERE login=?", (username,))
        row = c.fetchone()
    if not row:
        return None, "❌ Nieprawidłowy login lub hasło."

    user_id, hashed_password, imie_nazwisko, attempts, lock_until = row

    # 1. Sprawdzenie blokady czasowej
    if lock_until:
        lock_time = datetime.strptime(lock_until, "%Y-%m-%d %H:%M:%S")
        if datetime.now() < lock_time:
            pozostalo = int((lock_time - datetime.now()).total_seconds() / 60)
            return None, f"⚠️ Konto zablokowane. Spróbuj za {pozostalo} min."

    # 2. Weryfikacja hasła
    haslo_z_pieprzem = (provided_password + PEPPER).encode('utf-8')
    
    if bcrypt.checkpw(haslo_z_pieprzem, hashed_password):
        # SUKCES: Zerujemy licznik błędów
        with closing(get_db_connection()) as conn:
            conn.execute("UPDATE uzytkownicy SET failed_attempts = 0, lock_until = NULL WHERE id = ?", (user_id,))
            conn.commit()
        return (user_id, imie_nazwisko), "OK"
    else:
        # BŁĄD: Zwiększamy licznik
        nowe_attempts = attempts + 1
        nowa_blokada = None
        
        if nowe_attempts >= 5:
            nowa_blokada = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
            msg = "🚨 Zbyt wiele prób. Konto zablokowane na 15 minut."
        else:
            msg = f"❌ Błędne hasło. Pozostało prób: {5 - nowe_attempts}"

        with closing(get_db_connection()) as conn:
            conn.execute("UPDATE uzytkownicy SET failed_attempts = ?, lock_until = ? WHERE id = ?", 
                         (nowe_attempts, nowa_blokada, user_id))
            conn.commit()
        time.sleep(2) # Spowolnienie ataku
        return None, msg

def delete_user(user_id):
    """Usuwa pracownika z bazy. Głównego administratora (ID 1) nie można usunąć."""
    if user_id == 1:
        return False, "Nie można usunąć głównego administratora!"
    try:
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM uzytkownicy WHERE id = ?", (user_id,))
            conn.commit()
        return True, "Użytkownik został usunięty."
    except Exception as e:
        return False, f"Wystąpił błąd: {str(e)}"
    
def init_db():
    """Inicjalizacja bazy - jedna czysta i pełna wersja."""
    with closing(get_db_connection()) as conn:
        # Włączenie trybu WAL dla lepszej wydajności współbieżnej
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        
        # Tworzymy tabelę od razu ze wszystkimi kolumnami (failed_attempts, lock_until)
        c.execute('''CREATE TABLE IF NOT EXISTS uzytkownicy 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      login TEXT UNIQUE, 
                      password BLOB, 
                      imie_nazwisko TEXT,
                      failed_attempts INTEGER DEFAULT 0,
                      lock_until TEXT)''')
                     
        c.execute('''CREATE TABLE IF NOT EXISTS wizyty (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        session_id TEXT UNIQUE,
                        data_utworzenia TEXT,
                        typ_notatki TEXT,
                        tresc TEXT,
                        zatwierdzona INTEGER DEFAULT 0,
                        FOREIGN KEY(user_id) REFERENCES uzytkownicy(id))''')
        conn.commit()
    # Próba utworzenia admina z .env
    admin_login = os.getenv("ADMIN_LOGIN")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if admin_login and admin_password:
        # UWAGA: create_user sam sprawdza czy login istnieje, 
        # ale jeśli masz stary hash, to go nie podmieni. 
        # Dlatego musisz zrobić reset, o którym piszę niżej.
        create_user(admin_login, admin_password, 'Administrator Systemu')

# Wywołujemy funkcję
init_db()

def cleanup_old_visits(days_to_keep=7):
    """Automatycznie usuwa z bazy wizyty starsze niż podana liczba dni."""
    try:
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            # SQLite ma wbudowaną obsługę dat, potrafi sam odjąć dni
            c.execute("DELETE FROM wizyty WHERE data_utworzenia <= datetime('now', ?)", (f'-{days_to_keep} days',))
            deleted_rows = c.rowcount
            conn.commit()
            # Opcjonalnie: logujemy fakt usunięcia do pliku audytowego, jeśli coś usunięto
            if deleted_rows > 0:
                app_logger.info(f"SYSTEM_CLEANUP | STATUS: SUCCESS | Usunięto {deleted_rows} starych wizyt (starszych niż {days_to_keep} dni).")
    except Exception as e:
        app_logger.error(f"SYSTEM_CLEANUP | STATUS: FAILED | Błąd: {e}")
cleanup_old_visits(1) 
@st.cache_resource
def load_leki_list():
    file_path = os.path.join(BASE_DIR, "leki_pro.csv")
    if not os.path.exists(file_path):
        st.error(f"⚠️ Nie znaleziono bazy leków: {file_path}")
        st.warning("Aplikacja będzie działać, ale weryfikacja nazw medycznych jest wyłączona.")
        return []
    
    try:
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader) 
            return [row[0] for row in reader if row]
    except Exception as e:
        st.error(f"❌ Błąd podczas odczytu bazy: {e}")
        return []

LEKI_DATABASE = load_leki_list()

# ==========================================
# --- EKRAN LOGOWANIA (INTERFEJS) ---
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None
if 'user_name' not in st.session_state:
    st.session_state['user_name'] = ""

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
def generate_fhir_json(soap_text, patient_id="PACJENT-001"):
    """
    Wersja realistyczna: Wysyła całą notatkę jako jeden spójny dokument ClinicalNote.
    """
    import base64

    # Kodujemy tekst do Base64 (szpitale tak przesyłają dokumenty, by nie psuć znaków)
    encoded_note = base64.b64encode(soap_text.encode('utf-8')).decode('utf-8')

    fhir_resource = {
        "resourceType": "DocumentReference",
        "id": str(uuid.uuid4()),
        "status": "current",
        "type": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "11506-3",
                "display": "Provider-unspecified Progress note"
            }]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "description": "Notatka medyczna SafeMed AI",
        "content": [
            {
                "attachment": {
                    "contentType": "text/plain",
                    "data": encoded_note
                }
            }
        ]
    }

    return json.dumps(fhir_resource, indent=2, ensure_ascii=False)
    
def validate_medical_text(text):
    if not LEKI_DATABASE or not text:
        return text
    
    # 1. Szukamy listy leków (po ### lub ostatniej linii z przecinkami)
    meds_raw = ""
    if "###" in text:
        meds_raw = text.split("###")[-1]
    else:
        lines = text.strip().split('\n')
        if len(lines) > 0 and ',' in lines[-1]:
            meds_raw = lines[-1]
            
    if not meds_raw:
        return text

    # 2. Czyścimy listę leków od AI
    meds_to_check = [m.strip().strip(".,") for m in meds_raw.split(",") if len(m.strip()) > 2]
    
    # Pracujemy na całym tekście (nie odcinamy nic, żeby nic nie zginęło)
    validated_text = text
    
    # 3. Pętla sprawdzająca każdy lek z listy AI w całym tekście notatki
    for med in set(meds_to_check):
        # Szukamy w Twoim CSV (RPL)
        match_tuple = process.extractOne(med.upper(), LEKI_DATABASE)
        
        if match_tuple:
            score = match_tuple[1]
            # \b zapewnia, że nie podmienimy fragmentu słowa
            pattern = rf'\b{re.escape(med)}\b'
            
            if score >= 90:
                # Zamieniamy na zielony w KAŻDYM miejscu, gdzie występuje to słowo
                validated_text = re.sub(pattern, f"✅ {med}", validated_text, flags=re.IGNORECASE)
            else:
                # Zamieniamy na ostrzeżenie
                validated_text = re.sub(pattern, f"⚠️ **{med}**", validated_text, flags=re.IGNORECASE)
                
    return validated_text

# Inicjalizacja stanu sesji
if 'note_content' not in st.session_state:
    st.session_state['note_content'] = None

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
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = None
    st.session_state['user_name'] = ""
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
                user_data, status = check_login(st.session_state.get('user_login'), st_old)
                if user_data:
                    is_ok, msg = is_password_strong(st_new)
                    if is_ok:
                        new_hashed = bcrypt.hashpw((st_new + PEPPER).encode('utf-8'), bcrypt.gensalt(rounds=14))
                        try:
                            with closing(get_db_connection()) as conn:
                                cursor = conn.cursor()
                                cursor.execute("UPDATE uzytkownicy SET password = ? WHERE id = ?",
                                             (new_hashed, st.session_state['user_id']))
                                if cursor.rowcount > 0:
                                    conn.commit()
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
            with closing(get_db_connection()) as conn:
                c = conn.cursor()
                c.execute("SELECT id, login, imie_nazwisko FROM uzytkownicy")
                personel = c.fetchall()

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
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        dzis = datetime.now().strftime("%Y-%m-%d")
        c.execute(
            "SELECT session_id, data_utworzenia, typ_notatki, tresc FROM wizyty WHERE data_utworzenia LIKE ? AND user_id = ? ORDER BY id DESC",
            (f"{dzis}%", st.session_state['user_id'])
        )
        historia = c.fetchall()
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
                    st.session_state['note_content'] = row[3]
                    st.session_state['current_session'] = row[0]
                    st.rerun()
except Exception as e:
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
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_file.write(uploaded_file.getbuffer())
                temp_filename = tmp_file.name

            with open(temp_filename, "rb") as f:
                response = requests.post(
                    f"{WHISPER_URL}/async",
                    files={"file": f},
                    timeout=120
                )

        if response.status_code == 200:
            st.session_state["whisper_task_id"] = response.json()["task_id"]
            st.session_state["temp_filename"] = temp_filename
            st.rerun()
        else:
            st.error(f"❌ Błąd komunikacji z serwerem Whisper (Kod: {response.status_code}).")

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
            base_whisper = WHISPER_URL.replace("/transcriptions", "")
            res = requests.get(
                f"{base_whisper}/transcriptions/status/{task_id}",
                timeout=15
            )
            res.raise_for_status()
            data = res.json()

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

                        with closing(get_db_connection()) as conn:
                            c = conn.cursor()
                            c.execute("""
                                INSERT OR REPLACE INTO wizyty
                                (user_id, session_id, data_utworzenia, typ_notatki, tresc)
                                VALUES (?, ?, ?, ?, ?)
                            """, (
                                st.session_state["user_id"],
                                current_session,
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                st.session_state["selected_mode"],
                            clean_response
                            ))
                            conn.commit()

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
            final_display = validate_medical_text(raw_note) or raw_note
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
            st.session_state['note_content'] = None
            with global_model_lock:
                clear_vram()
            gc.collect()
            current_id = st.session_state.get('current_session', 'N/A')
            log_audit("USER_SESSION_RESET", "SUCCESS", current_id)
            st.rerun()
    else:
        st.error("Wystąpił błąd przy wyświetlaniu notatki.")
    

# --- ADRESY DLA MAC STUDIO W SIECI LOKALNEJ ---
# Jeśli Mac ma IP 192.168.1.50, to adresy będą wyglądać tak:
# WHISPER_SERVER_URL = "http://192.168.1.50:8000/v1/audio/transcriptions"
# client = OpenAI(base_url="http://192.168.1.50:1234/v1", api_key="lm-studio")