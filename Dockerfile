# Używamy Pythona w wersji slim (lekki)
FROM python:3.10-slim

# Instalujemy FFmpeg (niezbędny do audio)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Ustawiamy folder roboczy
WORKDIR /app

# Kopiujemy plik z bibliotekami i instalujemy je
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiujemy resztę Twojego kodu
COPY . .

# Otwieramy port Streamlita
EXPOSE 8501

# Komenda startowa
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]