# -*- coding: utf-8 -*-
import os
import sys
import time
import subprocess
import re

def kill_previous_processes():
    print("Eski işlemler temizleniyor...")
    if os.name == "nt":
        os.system("taskkill /F /IM streamlit.exe >nul 2>&1")
        os.system("taskkill /F /IM ssh.exe >nul 2>&1")
    else:
        os.system("pkill -f streamlit")
        os.system("pkill -f pinggy")
    
    if os.path.exists("pinggy_log.txt"):
        try: os.remove("pinggy_log.txt")
        except: pass

def main():
    kill_previous_processes()
    time.sleep(2)

    print("Streamlit V2 baslatiliyor...")
    subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"])
    time.sleep(5)

    print("Pinggy tuneli baslatiliyor...")
    if os.name == "nt":
        cmd = "start /B ssh -p 443 -R0:localhost:8501 -o StrictHostKeyChecking=no -o ServerAliveInterval=30 a.pinggy.io > pinggy_log.txt 2>&1"
    else:
        cmd = "ssh -p 443 -R0:localhost:8501 -o StrictHostKeyChecking=no -o ServerAliveInterval=30 a.pinggy.io > pinggy_log.txt 2>&1 &"
    
    os.system(cmd)

    url_found = False
    for _ in range(20):
        time.sleep(1)
        if os.path.exists("pinggy_log.txt"):
            with open("pinggy_log.txt", "r") as f:
                log_content = f.read()
                urls = re.findall(r"https://[a-zA-Z0-9-]+\.a\.free\.pinggy\.link", log_content)
                if urls:
                    print("\n" + "="*65)
                    print("🚀 QWENRAGGITY V2 SISTEMI HAZIR!")
                    print("ARAYÜZE GİRMEK İÇİN TIKLAYIN:")
                    print(f"👉 {urls[0]}")
                    print("="*65)
                    url_found = True
                    break

    if not url_found:
        print("\n⚠️ Tunel olusturulamadi. Log detaylari:")
        if os.path.exists("pinggy_log.txt"):
            with open("pinggy_log.txt", "r") as f:
                print(f.read())

if __name__ == "__main__":
    main()
