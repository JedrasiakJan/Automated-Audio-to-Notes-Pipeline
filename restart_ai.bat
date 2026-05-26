@echo off
cd /d "C:\Users\uczen\Desktop\Projekt whisper"
docker-compose restart

# Krok B: Ustaw Harmonogram Zadań (Windows Task Scheduler)

Kliknij Start, wpisz Harmonogram zadań i otwórz go.

Po prawej kliknij Utwórz zadanie podstawowe.

Nazwa: Restart AI Medical.

Wyzwalacz: Codziennie, godzina 03:00.

Akcja: Uruchom program.

Wskaż swój plik restart_ai.bat.

Ważne: W ostatnim kroku zaznacz "Otwórz okno właściwości...", a tam wybierz "Uruchom z najwyższymi uprawnieniami". Dzięki temu Windows nie zapyta o zgodę administratora w nocy.