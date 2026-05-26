import subprocess
import sys
import time
import signal

def run_services():
    # 1. Uruchomienie Serwera Whisper
    print("🚀 Uruchamiam Serwer Whisper (Port 8000)...")
    whisper_proc = subprocess.Popen([sys.executable, "whisper_server.py"])

    # Krótka pauza, żeby Whisper zdążył zająć port
    time.sleep(3)

    # 2. Uruchomienie Streamlit
    print("🚀 Uruchamiam Interfejs Streamlit...")
    # Używamy python -m streamlit run, aby mieć pewność co do środowiska
    streamlit_proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py"])

    print("\n✅ System SafeMed AI działa!")
    print("Naciśnij Ctrl+C, aby zamknąć wszystkie usługi naraz.\n")

    try:
        # Czekaj w pętli, aż użytkownik przerwie działanie
        while True:
            time.sleep(1)
            # Sprawdzanie czy procesy nie padły
            if whisper_proc.poll() is not None:
                print("❌ Serwer Whisper przestał działać!")
                break
            if streamlit_proc.poll() is not None:
                print("❌ Streamlit przestał działać!")
                break
    except KeyboardInterrupt:
        print("\n🛑 Zamykanie systemu...")
    finally:
        # Zabijanie procesów przy wyjściu
        whisper_proc.terminate()
        streamlit_proc.terminate()
        print("👋 Do zobaczenia!")

if __name__ == "__main__":
    run_services()

# --- UWAGI DLA MAC STUDIO (macOS) ---
# 1. Na Macu nie zadziała komenda 'taskkill'. Używamy 'pkill -f python'.
# 2. Ścieżka do FFMPEG na Macu zazwyczaj nie jest potrzebna, jeśli zainstalujesz go przez 'brew install ffmpeg'.
# 3. Komenda uruchamiająca streamlit pozostaje taka sama:
# streamlit_proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py"])

# Instalacja Homebrew (menedżer pakietów na Mac)
# /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Instalacja FFMPEG (niezbędne do dźwięku)
# brew install ffmpeg

# Instalacja bibliotek pod Apple Silicon (szybszy Whisper)
# pip install faster-whisper