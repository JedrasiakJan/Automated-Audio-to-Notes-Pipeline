@echo off
title SafeMed AI - System Launcher
color 0A

echo ==========================================
echo    STARTOWANIE SYSTEMU SAFEMED AI
echo ==========================================

:: Przejdź do folderu z projektem
cd /d "%USERPROFILE%\Desktop\Projekt whisper"

echo [!] Upewnij sie, ze LM Studio dziala na porcie 1234...
timeout /t 3

echo [🚀] Odpalam serwery i interfejs...
call venv\Scripts\activate
python run_all.py

pause