import re
import time
import bcrypt
from contextlib import closing
from datetime import datetime, timedelta
from typing import Optional

from core.config import PEPPER
from core.logging_config import app_logger
from db.connection import get_db_connection

AuthUserData = tuple[int, str]
LoginResult = tuple[Optional[AuthUserData], str]


def _hash_password(plaintext_password: str) -> bytes:
    return bcrypt.hashpw(
        (plaintext_password + PEPPER).encode("utf-8"),
        bcrypt.gensalt(rounds=14),
    )


def is_password_strong(password: str) -> tuple[bool, str]:
    if len(password) < 12:
        return False, "Hasło musi mieć co najmniej 12 znaków."
    if not re.search(r"\d", password):
        return False, "Hasło musi zawierać przynajmniej jedną cyfrę."
    if not re.search(r"[A-Z]", password):
        return False, "Hasło musi zawierać przynajmniej jedną wielką literę."
    if not re.search(r"[a-z]", password):
        return False, "Hasło musi zawierać przynajmniej jedną małą literę."
    return True, ""


def create_user(login: str, plaintext_password: str, imie_nazwisko: str) -> tuple[bool, str]:
    try:
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM uzytkownicy WHERE login = ?", (login,))
            if c.fetchone():
                return False, "Użytkownik o takim loginie już istnieje."

            hashed_password = _hash_password(plaintext_password)
            c.execute(
                """
                INSERT INTO uzytkownicy (login, password, imie_nazwisko)
                VALUES (?, ?, ?)
                """,
                (login, hashed_password, imie_nazwisko),
            )
            conn.commit()
            return True, "Użytkownik został utworzony."
    except Exception as e:
        app_logger.error(f"Błąd przy tworzeniu użytkownika {login}: {e}")
        return False, "Wystąpił błąd podczas tworzenia użytkownika."


def check_login(username: str, provided_password: str) -> LoginResult:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT id, password, imie_nazwisko, failed_attempts, lock_until
            FROM uzytkownicy
            WHERE login = ?
            """,
            (username,),
        )
        row = c.fetchone()

    if not row:
        time.sleep(1)
        return None, "❌ Nieprawidłowy login lub hasło."

    user_id, hashed_password, imie_nazwisko, attempts, lock_until = row

    if lock_until:
        lock_time = datetime.strptime(lock_until, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        if now < lock_time:
            pozostalo_min = max(1, int((lock_time - now).total_seconds() / 60))
            return None, f"⚠️ Konto zablokowane. Spróbuj za {pozostalo_min} min."

    password_with_pepper = (provided_password + PEPPER).encode("utf-8")
    is_valid = bcrypt.checkpw(password_with_pepper, hashed_password)

    if is_valid:
        with closing(get_db_connection()) as conn:
            conn.execute(
                """
                UPDATE uzytkownicy
                SET failed_attempts = 0, lock_until = NULL
                WHERE id = ?
                """,
                (user_id,),
            )
            conn.commit()
        return (user_id, imie_nazwisko), "OK"

    new_attempts = attempts + 1
    new_lock_until = None

    if new_attempts >= 5:
        new_lock_until = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        msg = "🚨 Zbyt wiele prób. Konto zablokowane na 15 minut."
    else:
        msg = f"❌ Błędne hasło. Pozostało prób: {5 - new_attempts}"

    with closing(get_db_connection()) as conn:
        conn.execute(
            """
            UPDATE uzytkownicy
            SET failed_attempts = ?, lock_until = ?
            WHERE id = ?
            """,
            (new_attempts, new_lock_until, user_id),
        )
        conn.commit()

    time.sleep(2)
    return None, msg


def change_password(user_id: int, new_password: str) -> bool:
    new_hashed = _hash_password(new_password)

    with closing(get_db_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE uzytkownicy
            SET password = ?, failed_attempts = 0, lock_until = NULL
            WHERE id = ?
            """,
            (new_hashed, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_user(user_id: int) -> tuple[bool, str]:
    if user_id == 1:
        return False, "Nie można usunąć głównego administratora!"

    try:
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM uzytkownicy WHERE id = ?", (user_id,))
            conn.commit()

            if c.rowcount == 0:
                return False, "Nie znaleziono użytkownika."

        return True, "Użytkownik został usunięty."
    except Exception as e:
        app_logger.error(f"Błąd przy usuwaniu użytkownika {user_id}: {e}")
        return False, "Wystąpił błąd podczas usuwania użytkownika."


def get_all_users() -> list[tuple[int, str, str]]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT id, login, imie_nazwisko FROM uzytkownicy ORDER BY id ASC")
        return c.fetchall()
    


def get_user_by_login(login: str) -> Optional[tuple[int, str, str]]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT id, login, imie_nazwisko
            FROM uzytkownicy
            WHERE login = ?
            """,
            (login,),
        )
        return c.fetchone()


def change_password_by_login(login: str, new_password: str) -> tuple[bool, str]:
    user = get_user_by_login(login)
    if not user:
        return False, f"Nie znaleziono użytkownika o loginie '{login}'."

    user_id = user[0]
    changed = change_password(user_id, new_password)

    if not changed:
        return False, "Nie udało się zmienić hasła."

    return True, f"Hasło dla '{login}' zostało pomyślnie zmienione."