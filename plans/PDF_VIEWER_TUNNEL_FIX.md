# PDF Viewer & Tunnel Erişilebilirlik Planı

**Hedef:** `streamlit-pdf-viewer` custom component'in proxy arkasında (`Pinggy`) yarattığı dinamik JS modül yükleme hatasını çözmek ve sistemin kolayca erişilebilir olmasını sağlamak.

**Durum:** Planlama Aşaması

---

## 📋 Mevcut Durum

### Sorun
```
TypeError: error loading dynamically imported module: https://issvb-185-113-122-75.run.pinggy-free.link/static/js/ComponentInstance.bRCLuLlX.js
```

### Kök Neden Analizi

**Custom Component Mekanizması:**
- `streamlit-pdf-viewer` (>=0.0.29) Streamlit'in `components.v1` API'sini kullanır.
- Ön yüz React/Vite ile build edilmiş, dinamik `import()` ile chunk'lar yüklenir (lazy loading).
- Component iframe üzerinden `/component/streamlit_pdf_viewer/...` URL'inde sunulur.
- Vite/Webpack build çıktısı: `ComponentInstance.bRCLuLlX.js` (hash'li filename).

**Proxy Sorunu:**
- Pinggy-free.link tüneli `ssh -R0:localhost:8501 -p 443 a.pinggy.io` ile kurulur.
- URL: `https://issvb-185-113-122-75.run.pinggy-free.link`
- Pinggy, HTTP header'ları (`X-Forwarded-Proto`, `X-Forwarded-Host`) düzgün iletmez veya Streamlit bu header'ları yanlış yorumlar.
- Tarayıcı component'in JS chunk'ını yüklemeye çalıştığında:
  - Ya yanlış host/path'e istek atar
  - Ya CORS/mixed-content hatası alır
  - Ya `import()` Promise'i reddedilir ve `TypeError` olarak görünür

**Streamlit Config Eksikliği:**
- `~/.streamlit/config.toml` yok veya proxy ayarları yapılmamış.
- `server.baseUrlPath`, `server.enableCORS` gibi ayarlar eksik.

---

## 🎯 Çözüm Planı

### Adım 1: streamlit-pdf-viewer Bağımlılığını Kaldır (Kritik)

**Sorun:** Custom component + proxy kombinasyonu teknik olarak güvenilir çalışmıyor.

**Çözüm:** PDF'i custom component olmadan göster. İki seçenek:

#### Seçenek A: Base64 + HTML Embed (Önerilen)
```python
# app.py'de pdf_viewer() çağrısının yerine:
import streamlit as st
import base64

def render_pdf_base64(pdf_bytes, page=1, width=700):
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_url = f"data:application/pdf;base64,{b64}"
    st.components.v1.html(
        f"""
        <iframe src="{pdf_url}" width="{width}" height="900" style="border:none;"></iframe>
        """,
        height=950,
        scrolling=True
    )
```

#### Seçenek B: PyMuPDF ile Sayfa Görüntüsü
```python
import fitz
from PIL import Image
import io

def render_pdf_page_as_image(pdf_path, page_num=1, width=700):
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]
    mat = fitz.Matrix(2.0, 2.0)  # 2x zoom
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    st.image(img_bytes, use_container_width=True)
    doc.close()
```

**Avantajları:**
- Custom component yok → proxy sorunu yok
- Sadece Python backend kullanılıyor
- Her tünelde (Pinggy, Cloudflare, ngrok, LocalTunnel) çalışır
- Streamlit'in native `st.components.v1.html` ile PDF render

---

### Adım 2: runner.py'yi Cloudflare Tunnel'a Geçir (Tavsiye Edilen)

**Sorun:** Pinggy:
- Rastgele URL üretir (bookmark zor)
- Bağlantı zamanla kopabilir
- `X-Forwarded-*` header yönetimi zayıf
- HTTP/2 ve WebSocket desteği sınırlı

**Çözüm:** `cloudflared` kullan. Kurulum:
```bash
# Vast.ai sunucusunda bir kere:
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Test:
cloudflared tunnel --url http://localhost:8501
```

**runner.py değişikliği:**
```python
# runner.py - Pinggy yerine Cloudflare Tunnel
def main():
    kill_previous_processes()
    time.sleep(2)

    print("Streamlit V2 baslatiliyor...")
    subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py",
                      "--server.port", "8501", "--server.address", "0.0.0.0",
                      "--server.enableCors=false"])
    time.sleep(5)

    print("Cloudflare Tunnel baslatiliyor...")
    # cloudflared loglarını yakala
    log_file = open("cloudflared_log.txt", "w")
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", "http://localhost:8501",
         "--logfile", "cloudflared_log.txt", "--metrics", "localhost:53121"],
        stdout=log_file, stderr=subprocess.STDOUT
    )
    
    # URL'yi yakala (10 sn içinde)
    for _ in range(20):
        time.sleep(1)
        if os.path.exists("cloudflared_log.txt"):
            with open("cloudflared_log.txt", "r") as f:
                content = f.read()
                # cloudflared "Your tunnel D1B8... is now running at https://xxxx.trycloudflare.com" formatında URL verir
                match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", content)
                if match:
                    print(f"\n🚀 TUNNEL URL: {match.group(0)}")
                    break
```

**Avantajları:**
- Ücretsiz
- Sabit URL yok ama `trycloudflare.com` üzerinden anlık URL verir
- SSL/TLS termination otomatik
- `X-Forwarded-*` header'ları düzgün
- WebSocket desteği var
- Daha stabil bağlantı

---

### Adım 3: Streamlit Config Oluştur (Önerilen)

**Dosya:** `~/.streamlit/config.toml` (sunucuda)

```toml
[server]
port = 8501
headless = true
enableCORS = false
enableXsrfProtection = false
enableWebsocketCompression = true

[browser]
serverAddress = "localhost:8501"
gatherUsageStats = false

[theme]
primaryColor = "#4285F4"
backgroundColor = "#0e1117"
```

---

### Adım 4: requirements.txt Güncelle (Gerekirse)

Eğer Seçenek B kullanılacaksa:
```
PyMuPDF  # zaten var
```

`streamlit-pdf-viewer` bağımlılığı kaldırılabilir veya bırakılabilir (app.py'de kullanılmadığı sürece sorun olmaz).

---

## 📐 app.py Değişiklikleri

### Mevcut (Sorunlu):
```python
with c2:
    st.title("📄 Kaynak İzleyici")
    if st.session_state.viewer_pdf_path and os.path.exists(st.session_state.viewer_pdf_path):
        with open(st.session_state.viewer_pdf_path, "rb") as f:
            pdf_viewer(f.read(), width=700, pages_to_render=[st.session_state.viewer_page])
```

### Yeni (Çalışır):
```python
def render_pdf_base64(pdf_path, page_num=1, width=700):
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_url = f"data:application/pdf;base64,{b64}"
    st.components.v1.html(
        f"""
        <iframe src="{pdf_url}" width="{width}" height="900" style="border:none;"></iframe>
        """,
        height=950,
        scrolling=True
    )

def render_pdf_page_image(pdf_path, page_num=1, width=700):
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    st.image(buf.getvalue(), use_container_width=True)
    doc.close()

# Kullanım:
with c2:
    st.title("📄 Kaynak İzleyici")
    if st.session_state.viewer_pdf_path and os.path.exists(st.session_state.viewer_pdf_path):
        tab1, tab2 = st.tabs(["🌐 PDF Görüntüle", "🖼️ Sayfa Görüntüsü"])
        with tab1:
            render_pdf_base64(st.session_state.viewer_pdf_path, 
                            page_num=st.session_state.viewer_page)
        with tab2:
            render_pdf_page_image(st.session_state.viewer_pdf_path,
                                 page_num=st.session_state.viewer_page,
                                 width=700)
```

---

## 🔧 runner.py Değişiklikleri

### Değişecek Kısımlar:
1. Pinggy komutu → Cloudflared komutu
2. URL yakalama regex'i → `trycloudflare.com` formatı
3. Gereksiz `pkill pinggy` → `pkill cloudflared`

---

## 📊 Uygulama Sırası

| Sıra | Adım | Öncelik | Not |
|------|------|---------|-----|
| 1 | `app.py`'de `pdf_viewer` → base64 embed | Kritik | Custom component bağımlılığını kaldır |
| 2 | `requirements.txt`'den `streamlit-pdf-viewer` kaldır (opsiyonel) | Orta | Kullanılmıyor zaten |
| 3 | `runner.py`'yi Cloudflare Tunnel'a geçir | Yüksek | Pinggy yerine cloudflared |
| 4 | Sunucuya `~/.streamlit/config.toml` deploy et | Orta | Proxy header ayarları |
| 5 | Test: PDF yükle, işle, yanıtla, PDF görüntüle | Kritik | Uçtan uca test |

---

## ✅ Doğrulama Testleri

### Test 1: Yerel
```bash
streamlit run app.py
# localhost:8501'dc aç, PDF yükle, işle, soru sor, PDF görüntülenmeli
```

### Test 2: Uzak (Cloudflare Tunnel)
```bash
python runner.py
# trycloudflare.com URL'sini al
# URL'yi tarayıcıda aç
# Aynı işlemleri yap
# Hata olmamalı
```

### Test 3: Bağlantı Stabilitesi
```bash
# 30 dakika boyunca bağlantıyı canlı tut
# Kopma olmamalı
```

---

## ⚠️ Dikkat Edilecekler

1. **Base64 embed büyük dosyalarda yavaş olabilir.** >10MB PDF'ler için sayfa görüntüsü (Seçenek B) daha performanslı.
2. **Cloudflare Tunnel ücretsiz planda sabit URL yok.** Her bağlantıda yeni URL üretir. Sabit URL için DNS veya CF Teams gerekli (ücretli).
3. **ngrok ücretsiz planda `http` requirement var.** `ngrok http 8501` çalışır ama header rewrite için `-host-header=rewrite` gerekli.
4. **LocalTunnel (`lt`) stability sorunu var.** Zorunlu kalınırsa kullanılabilir ama CF önerilir.

---

## 📝 Alternatif: ngrok (Eğer Cloudflare Çalışmazsa)

```python
# runner.py ngrok versiyonu:
cmd = "cloudflared tunnel --url http://localhost:8501"
# veya ngrok:
cmd = "ngrok http 8501 --host-header=rewrite"
```

---

**Plan Versiyonu:** 1.0  
**Oluşturulma Tarihi:** 2026-05-17  
**Durum:** Uygulama Bekleniyor