# -*- coding: utf-8 -*-
import os
import sys
import time
import subprocess
import re

def kill_previous_processes():
    print("Eski islemler temizleniyor...")
    if os.name == "nt":
        os.system("taskkill /F /IM streamlit.exe >nul 2>&1")
        os.system("taskkill /F /IM ssh.exe >nul 2>&1")
    else:
        os.system("pkill -f streamlit")
        os.system("pkill -f pinggy")

    for f in ["pinggy_log.txt"]:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

def main():
    kill_previous_processes()
    time.sleep(2)

    print("Streamlit V2 baslatiliyor...")
    subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py",
                      "--server.port", "8501", "--server.address", "0.0.0.0",
                      "--server.enableCors=false"])
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
                content = f.read()
                match = re.search(r"https://[a-zA-Z0-9-]+\.a\.free\.pinggy\.link", content)
                if match:
                    print("\n" + "="*65)
                    print("🚀 QWENRAGGITY V2 SISTEMI HAZIR!")
                    print("ARAYUZE GIRMEK İCİN TIKLAYIN:")
                    print(f"👉 {match.group(0)}")
                    print("="*65)
                    url_found = True
                    break

    if not url_found:
        print("\n⚠️ Tunnel olusturulamadi. Log detaylari:")
        if os.path.exists("pinggy_log.txt"):
            with open("pinggy_log.txt", "r") as f:
                print(f.read())

if __name__ == "__main__":
    main()
