# 1. Temel İmaj: Python yüklü hafif bir Linux (Slim)
FROM python:3.10-slim

# 2. Gerekli Sistem Araçlarını ve Chrome'u Kur
# DrissionPage için Chromium ve Xvfb (Sanal Ekran) lazım.
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# 3. Çalışma Klasörünü Ayarla
WORKDIR /app

# 4. Kütüphaneleri Yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Kodları İçeri Kopyala
COPY . .

# 6. Ortam Değişkenleri (Ekran Ayarı)
ENV DISPLAY=:99

# 7. Başlatma Komutu
# Xvfb sanal ekranını açar ve scripti içinde çalıştırır.
CMD Xvfb :99 -screen 0 1920x1080x24 & python scrapper_turbo_v3.py