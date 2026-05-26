import getpass

from core.config import PEPPER  # wymusza obecność APP_PEPPER
from db.users import create_user, is_password_strong


def dodaj_nowego_lekarza() -> None:
    print("\n" + "=" * 45)
    print(" 🏥 PANEL REJESTRACJI PERSONELU (SafeMed AI) 🏥")
    print("=" * 45 + "\n")

    login = input("1. Podaj nowy login (np. j.nowak): ").strip()
    imie_nazwisko = input("2. Podaj imię i nazwisko: ").strip()

    if not login or not imie_nazwisko:
        print("\n❌ Błąd: Login i imię i nazwisko nie mogą być puste.")
        return

    print("\n🔐 Ustalanie bezpiecznego hasła (min. 12 znaków):")
    haslo = getpass.getpass("3. Wpisz hasło: ")

    is_ok, msg = is_password_strong(haslo)
    if not is_ok:
        print(f"\n❌ BŁĄD BEZPIECZEŃSTWA: {msg}")
        return

    potwierdz_haslo = getpass.getpass("4. Powtórz hasło: ")
    if haslo != potwierdz_haslo:
        print("\n❌ Błąd: Hasła nie są identyczne!")
        return

    print("\n⏳ Zapisywanie użytkownika w bazie...")

    success, message = create_user(
        login=login,
        plaintext_password=haslo,
        imie_nazwisko=imie_nazwisko,
    )

    if success:
        print(f"\n✅ SUKCES! {message}")
    else:
        print(f"\n❌ BŁĄD: {message}")


if __name__ == "__main__":
    _ = PEPPER
    dodaj_nowego_lekarza()