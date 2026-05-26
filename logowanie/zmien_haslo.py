import sqlite3
import bcrypt
import getpass
import os
from dotenv import load_dotenv

# Wczytujemy pieprz z pliku .env
load_dotenv()
PEPPER = os.getenv("APP_PEPPER", "DomyślnyKluczAwaryjny123") 

def zmien_haslo():
    print("\n" + "="*40)
    print(" 🔐 AWARYJNA ZMIANA HASŁA UŻYTKOWNIKA 🔐")
    print("="*40 + "\n")
    
    login = input("Podaj login użytkownika (np. szef_kliniki): ")
    
    print("\nUWAGA: Podczas wpisywania hasła nie pojawią się żadne znaki.")
    nowe_haslo = getpass.getpass("Wpisz NOWE hasło: ")
    potwierdz_haslo = getpass.getpass("Powtórz NOWE hasło: ")
    
    if nowe_haslo != potwierdz_haslo:
        print("\n❌ Błąd: Hasła nie są identyczne. Spróbuj ponownie.")
        return
        
    print("\n⏳ Generowanie nowego, bezpiecznego klucza...")
    
    # Mielenie nowego hasła z pieprzem i nową solą
    haslo_z_pieprzem = nowe_haslo + PEPPER
    haslo_bytes = haslo_z_pieprzem.encode('utf-8')
    hashed_password = bcrypt.hashpw(haslo_bytes, bcrypt.gensalt(rounds=14))
    
    try:
        with sqlite3.connect('historia_wizyt.db') as conn:
            c = conn.cursor()
            
            # Najpierw sprawdzamy, czy użytkownik w ogóle istnieje
            c.execute("SELECT id FROM uzytkownicy WHERE login=?", (login,))
            if not c.fetchone():
                print(f"\n❌ BŁĄD: Nie znaleziono użytkownika o loginie '{login}'!")
                return

            # Jeśli istnieje, nadpisujemy jego hasło (UPDATE zamiast INSERT)
            c.execute("UPDATE uzytkownicy SET password = ? WHERE login = ?", 
                      (hashed_password, login))
            conn.commit()
            
        print(f"\n✅ SUKCES! Hasło dla '{login}' zostało pomyślnie zmienione.")
        print("Możesz teraz zalogować się do aplikacji głównym hasłem.")
        
    except Exception as e:
        print(f"\n❌ BŁĄD SYSTEMU: {e}")

if __name__ == "__main__":
    zmien_haslo()