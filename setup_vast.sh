#!/bin/bash
set -e

echo "========================================================"
echo "🚀 QwenRaggity V2 - Vast.ai GPU Kurulum Scripti Başlıyor"
echo "========================================================"

# 1. Sistem Güncellemeleri ve Temel Araçlar
echo "📦 1. Sistem güncelleniyor ve temel araçlar kuruluyor..."
apt-get update && apt-get install -y psmisc curl wget git tmux vim jq htop libgl1-mesa-glx build-essential

# 2. Python ve Pip Kontrolü (Vast.ai imajlarında genelde vardır, emin olmak için güncelliyoruz)
echo "🐍 2. Python bağımlılıkları güncelleniyor..."
pip install --upgrade pip

# 3. CUDA Destekli PyTorch Kurulumu (Vast.ai'da genelde hazır gelir ama garantileyelim)
echo "🔥 3. CUDA destekli PyTorch ve Faiss-GPU kuruluyor..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install faiss-gpu

# 4. QwenRaggity V2 Kütüphaneleri
echo "📚 4. Gerekli Python kütüphaneleri kuruluyor..."
pip install streamlit transformers accelerate bitsandbytes rank_bm25 scikit-learn numpy Pillow langchain-text-splitters sentence-transformers docling streamlit-pdf-viewer networkx requests

# 5. Ollama Kurulumu
echo "🦙 5. Ollama kuruluyor..."
if ! command -v ollama &> /dev/null
then
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "Ollama zaten kurulu."
fi

# Ollama servisini arka planda başlat (eğer çalışmıyorsa)
echo "Ollama servisi başlatılıyor..."
ollama serve > ollama.log 2>&1 &
sleep 5 # Servisin ayağa kalkması için biraz bekle

# 6. Qwen 2.5 14B Modelini İndir (24 GB VRAM için harika seçim)
echo "🧠 6. Qwen2.5 14B modeli indiriliyor (Bu işlem internet hızına göre biraz sürebilir)..."
ollama pull qwen2.5:14b

echo "========================================================"
echo "✅ KURULUM TAMAMLANDI!"
echo "========================================================"
echo "Uygulamayı başlatmak için şu komutu çalıştırın:"
echo "python runner.py"
echo "Pinggy tüneli size bir link verecek, o linkten girebilirsiniz."
