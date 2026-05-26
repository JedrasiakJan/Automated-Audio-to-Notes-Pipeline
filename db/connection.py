import os
import sqlite3
from contextlib import closing

from core.config import BASE_DIR, ADMIN_LOGIN, ADMIN_PASSWORD

DB_PATH = os.path.join(BASE_DIR, "historia_wizyt.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    from db.users import create_user

    with closing(get_db_connection()) as conn:
        c = conn.cursor()

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS uzytkownicy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login TEXT UNIQUE NOT NULL,
                password BLOB NOT NULL,
                imie_nazwisko TEXT NOT NULL,
                failed_attempts INTEGER DEFAULT 0,
                lock_until TEXT
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS wizyty (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id TEXT UNIQUE NOT NULL,
                data_utworzenia TEXT NOT NULL,
                typ_notatki TEXT NOT NULL,
                tresc TEXT NOT NULL,
                zatwierdzona INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES uzytkownicy(id)
            )
            """
        )

        conn.commit()

    if ADMIN_LOGIN and ADMIN_PASSWORD:
        create_user(ADMIN_LOGIN, ADMIN_PASSWORD, "Administrator Systemu")