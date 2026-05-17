# Vast.ai QwenRaggity V2 Kurulum Rehberi

Bu rehber, kiraladığınız 24 GB VRAM'li Vast.ai sunucusunda **QwenRaggity V2** projenizi en hızlı şekilde ayağa kaldırmanızı sağlar.

## Adım 1: İmaj (Image) Seçimi
Vast.ai üzerinden makine kiralarken **PyTorch** imajını seçmeniz en iyisidir.
Önerilen İmaj: `pytorch/pytorch:2.1.0-cuda12.1-cudnn8-devel` (veya Vast.ai'nin önerdiği güncel Cuda Toolkit'li PyTorch imajı).

## Adım 2: Dosyaları Sunucuya Aktarma
VS Code Remote-SSH, WinSCP veya FileZilla gibi bir araçla `qwenraggity_v2` klasörünü sunucuya yükleyin.
*Vast.ai size bir IP, Port numarası ve kullanıcı adı (genelde `root`) verir.*

## Adım 3: Kurulumu Başlatma
Sunucuya SSH ile bağlandıktan sonra klasörün içine girin ve hazırladığım otomatik kurulum scriptini çalıştırın:

```bash
cd qwenraggity_v2
chmod +x setup_vast.sh
./setup_vast.sh
```

Bu script şunları otomatik yapar:
1. Temel Linux araçlarını günceller.
2. 24GB VRAM'de çok daha hızlı vektör araması için `faiss-gpu` kurar.
3. Tüm Python gereksinimlerini kurar.
4. Ollama'yı indirip kurar ve arka planda çalıştırır.
5. **Qwen 2.5 14B** modelini indirir (24 GB VRAM'in hakkını veren akıllı model).

## Adım 4: Sistemi Ayağa Kaldırma (Tünelleme)
Kurulum bittikten sonra uygulamanızı internete açmak (bilgisayarınızdan girebilmek) için runner dosyasını çalıştırın:

```bash
python runner.py
```

Ekrana şöyle bir çıktı gelecektir:
```text
🚀 QWENRAGGITY V2 SISTEMI HAZIR!
ARAYÜZE GİRMEK İÇİN TIKLAYIN:
👉 https://xxxx-xxxx.a.free.pinggy.link
```

Verilen adrese tıkladığınızda kendi cihazınızın tarayıcısından 24GB VRAM gücündeki sisteminize erişebilirsiniz!

## Notlar:
- Sistemi kapatıp açtığınızda Ollama servisinin çalıştığından emin olmak için `ollama serve &` komutunu çalıştırabilirsiniz.
- Model yeterince akıllıdır ancak 24GB VRAM ile ileride kodlarda oynama yaparak `qwen2.5:32b` (4-bit quantized) modelini de deneyebilirsiniz. Mevcut `14B` model kusursuz bir performans ve zeka dengesi sunacaktır.
