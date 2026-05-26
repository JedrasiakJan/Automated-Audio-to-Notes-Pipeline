from contextlib import closing
from datetime import datetime
from typing import Optional

from core.logging_config import app_logger
from db.connection import get_db_connection

VisitListRow = tuple[str, str, str, str]
VisitDetailsRow = tuple[int, int, str, str, str, str, int]


def cleanup_old_visits(days_to_keep: int = 7) -> None:
    try:
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            c.execute(
                "DELETE FROM wizyty WHERE data_utworzenia <= datetime('now', ?)",
                (f"-{days_to_keep} days",),
            )
            deleted_rows = c.rowcount
            conn.commit()

            if deleted_rows > 0:
                app_logger.info(
                    f"SYSTEM_CLEANUP | STATUS: SUCCESS | Usunięto {deleted_rows} starych wizyt "
                    f"(starszych niż {days_to_keep} dni)."
                )
    except Exception as e:
        app_logger.error(f"SYSTEM_CLEANUP | STATUS: FAILED | Błąd: {e}")


def save_visit(
    user_id: int,
    session_id: str,
    typ_notatki: str,
    tresc: str,
    data_utworzenia: Optional[str] = None,
) -> None:
    visit_date = data_utworzenia or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT OR REPLACE INTO wizyty
                (user_id, session_id, data_utworzenia, typ_notatki, tresc)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, session_id, visit_date, typ_notatki, tresc),
            )
            conn.commit()
    except Exception as e:
        app_logger.error(
            f"Błąd zapisu wizyty | user_id={user_id} | session_id={session_id} | error={e}"
        )
        raise


def get_today_visits_for_user(user_id: int) -> list[VisitListRow]:
    dzis = datetime.now().strftime("%Y-%m-%d")

    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT session_id, data_utworzenia, typ_notatki, tresc
            FROM wizyty
            WHERE data_utworzenia LIKE ? AND user_id = ?
            ORDER BY id DESC
            """,
            (f"{dzis}%", user_id),
        )
        return c.fetchall()


def get_visit_by_session_id(session_id: str) -> Optional[VisitDetailsRow]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT id, user_id, session_id, data_utworzenia, typ_notatki, tresc, zatwierdzona
            FROM wizyty
            WHERE session_id = ?
            """,
            (session_id,),
        )
        return c.fetchone()