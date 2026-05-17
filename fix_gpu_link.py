# -*- coding: utf-8 -*-
import os
import time
import subprocess
import re

def fix_all():
    print("========================================================")
    print("🛠️  QwenRaggity V2 - Vast.ai GPU & Link Sabitleyici")
    print("========================================================")

    # 1. GPU Sürücülerini Ollama'ya Tanıtma
    print("🔍 1. GPU kütüphaneleri kontrol ediliyor...")
    os.environ["OLLAMA_HOST"] = "127.0.0.1:11434"
    # Vast.ai Docker imajlarındaki standart NVIDIA kütüphane yolu
    os.environ["LD_LIBRARY_PATH"] = "/usr/lib/x86_64-linux-gnu:" + os.environ.get("LD_LIBRARY_PATH", "")

    # Eski Ollama süreçlerini temizle
    os.system("pkill -f ollama")
    time.sleep(2)
    
    # Ollama'yı arka planda GPU'yu görecek şekilde başlat
    print("🚀 2. Ollama GPU modunda başlatılıyor...")
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)
    
    # 2. Pinggy Tünelini Yeniden Başlat
    print("🔗 3. Pinggy tüneli yeniden kuruluyor...")
    os.system("pkill -f ssh") # Eski SSH tünellerini temizle
    time.sleep(2)
    
    # Yeni tüneli başlat ve log dosyasına yaz
    cmd = "ssh -p 443 -R0:localhost:8501 -o StrictHostKeyChecking=no -o ServerAliveInterval=30 a.pinggy.io > pinggy_log.txt 2>&1 &"
    os.system(cmd)

    # 3. Linki Yakalama Döngüsü
    print("⏳ 4. Giriş linki bekleniyor (max 30 sn)...")
    url_found = False
    for i in range(30):
        time.sleep(1)
        if os.path.exists("pinggy_log.txt"):
            with open("pinggy_log.txt", "r") as f:
                content = f.read()
                # Pinggy'nin ürettiği https linkini ara
                urls = re.findall(r"https://[a-zA-Z0-9-]+\.a\.free\.pinggy\.link", content)
                if urls:
                    print("\n" + "🚀"*20)
                    print("✅ SİSTEM BAŞARIYLA BAŞLATILDI!")
                    print(f"👉 GİRİŞ LİNKİNİZ: {urls[0]}")
                    print("🚀"*20 + "\n")
                    url_found = True
                    break
        if i % 5 == 0 and i > 0:
            print(f"... {i}. saniye, hala link aranıyor ...")

    if not url_found:
        print("\n⚠️ HATA: Link zaman aşımına uğradı.")
        print("Log dosyasının son 10 satırı:")
        os.system("tail -n 10 pinggy_log.txt")
        print("\nİpucu: 'pciutils' paketinin kurulu olduğundan emin olun (apt-get install -y pciutils).")

if __name__ == "__main__":
    fix_all()
