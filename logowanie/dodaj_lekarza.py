import sqlite3
import bcrypt
import getpass
import os
import re
from dotenv import load_dotenv

# --- WCZYTYWANIE PIEPRZU ---
load_dotenv()
PEPPER = os.getenv("APP_PEPPER", "DomyślnyKluczAwaryjny123") 

def is_password_strong(password):
    """Sprawdza, czy hasło spełnia standardy (12 znaków, cyfra, duża i mała litera)."""
    if len(password) < 12:
        return False, "Hasło musi mieć co najmniej 12 znaków."
    if not re.search(r"\d", password):
        return False, "Hasło musi zawierać przynajmniej jedną cyfrę."
    if not re.search(r"[A-Z]", password):
        return False, "Hasło musi zawierać przynajmniej jedną wielką literę."
    if not re.search(r"[a-z]", password):
        return False, "Hasło musi zawierać przynajmniej jedną małą literę."
    return True, ""

def dodaj_nowego_lekarza():
    print("\n" + "="*45)
    print(" 🏥 PANEL REJESTRACJI PERSONELU (SafeMed AI) 🏥")
    print("="*45 + "\n")
    
    # 1. Najpierw zbieramy dane podstawowe
    login = input("1. Podaj nowy login (np. j.nowak): ").strip()
    imie_nazwisko = input("2. Podaj imię i nazwisko: ").strip()
    
    if not login or not imie_nazwisko:
        print("\n❌ Błąd: Login i nazwisko nie mogą być puste!")
        return

    # 2. Potem zajmujemy się hasłem
    print("\n🔐 Ustalanie bezpiecznego hasła (min. 12 znaków):")
    haslo = getpass.getpass("3. Wpisz hasło: ")
    
    # Walidacja siły
    is_ok, msg = is_password_strong(haslo)
    if not is_ok:
        print(f"\n❌ BŁĄD BEZPIECZEŃSTWA: {msg}")
        return

    potwierdz_haslo = getpass.getpass("4. Powtórz hasło: ")
    
    if haslo != potwierdz_haslo:
        print("\n❌ Błąd: Hasła nie są identyczne!")
        return
        
    # 3. Proces zapisu
    print("\n⏳ Szyfrowanie i zapisywanie w bazie...")
    
    # Hashowanie z pieprzem
    haslo_z_pieprzem = (haslo + PEPPER).encode('utf-8')
    hashed_password = bcrypt.hashpw(haslo_z_pieprzem, bcrypt.gensalt(rounds=14))
    
    try:
        with sqlite3.connect('historia_wizyt.db') as conn:
            c = conn.cursor()
            # SQLite sam wstawi domyślne 0 dla failed_attempts i NULL dla lock_until
            c.execute("INSERT INTO uzytkownicy (login, password, imie_nazwisko) VALUES (?, ?, ?)", 
                      (login, hashed_password, imie_nazwisko))
            conn.commit()
            
        print(f"\n✅ SUKCES! Użytkownik {imie_nazwisko} dodany pomyślnie.")
        
    except sqlite3.IntegrityError:
        print(f"\n❌ BŁĄD: Login '{login}' jest już zajęty!")
    except Exception as e:
        print(f"\n❌ BŁĄD SYSTEMU: {e}")

if __name__ == "__main__":
    dodaj_nowego_lekarza()