FROM python:3.11-slim

# Instalujemy ffmpeg + libopus (do voice) + curl (opcjonalnie do deno jeśli potrzeba)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    libffi-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Opcjonalnie Deno jeśli yt-dlp narzeka na JS runtime (dodaj jeśli masz warning)
# RUN curl -fsSL https://deno.land/install.sh | sh
# ENV PATH="/root/.deno/bin:${PATH}"

WORKDIR /app

# Kopiujemy requirements najpierw → cache pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiujemy resztę kodu
COPY cookies.txt
COPY . .

# Uruchamiamy bota
CMD ["python", "main.py"]
