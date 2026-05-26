import getpass

from core.config import PEPPER  # wymusza obecność APP_PEPPER
from db.users import change_password_by_login, is_password_strong


def zmien_haslo() -> None:
    print("\n" + "=" * 40)
    print(" 🔐 AWARYJNA ZMIANA HASŁA UŻYTKOWNIKA 🔐")
    print("=" * 40 + "\n")

    login = input("Podaj login użytkownika (np. szef_kliniki): ").strip()
    if not login:
        print("\n❌ Błąd: Login nie może być pusty.")
        return

    print("\nUWAGA: Podczas wpisywania hasła nie pojawią się żadne znaki.")
    nowe_haslo = getpass.getpass("Wpisz NOWE hasło: ")
    potwierdz_haslo = getpass.getpass("Powtórz NOWE hasło: ")

    if nowe_haslo != potwierdz_haslo:
        print("\n❌ Błąd: Hasła nie są identyczne.")
        return

    is_ok, msg = is_password_strong(nowe_haslo)
    if not is_ok:
        print(f"\n❌ BŁĄD BEZPIECZEŃSTWA: {msg}")
        return

    print("\n⏳ Zapisywanie nowego hasła...")
    success, message = change_password_by_login(login, nowe_haslo)

    if success:
        print(f"\n✅ SUKCES! {message}")
        print("Możesz teraz zalogować się do aplikacji nowym hasłem.")
    else:
        print(f"\n❌ BŁĄD: {message}")


if __name__ == "__main__":
    _ = PEPPER
    zmien_haslo()