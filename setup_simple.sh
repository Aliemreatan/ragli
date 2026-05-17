#!/bin/bash
set -e

echo "========================================================"
echo "🚀 QwenRaggity V2 - Basit Kurulum (Requirements.txt)"
echo "========================================================"

# 1. Sistem Araçları
echo "📦 1. Sistem paketleri kuruluyor..."
apt-get update && apt-get install -y psmisc curl wget git libgl1-mesa-glx

# 2. Pip Güncelleme
echo "🐍 2. Pip güncelleniyor..."
pip install --upgrade pip

# 3. Requirements dosyasından kurulum
echo "📚 3. Python kütüphaneleri kuruluyor (Bu işlem sürer)..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "Hata: requirements.txt bulunamadı!"
    exit 1
fi

# 4. Ollama Kurulumu ve Model
echo "🦙 4. Ollama kontrol ediliyor..."
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
fi

echo "Ollama servisi başlatılıyor..."
ollama serve > ollama.log 2>&1 &
sleep 10

echo "🧠 5. Model indiriliyor (qwen2.5:14b)..."
ollama pull qwen2.5:14b

echo "✅ KURULUM TAMAMLANDI!"
