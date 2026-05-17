# Logging + Progress Bar Ekleme Planı

## Hedefler
1. Her chunk işlendiğinde debug dosyasına timestamp + fonksiyon adı + chunk snippet yaz
2. Streamlit önyüzünde tek progress bar üzerinden dosya + chunk birleşik ilerleme göster
3. Terminalde fonksiyon çağrıları, zamanları ve süreleri takip edilebilir ol

---

## 1. `logger_config.py` — Merkezi Logger

- **Çıktı dosyası:** `logs/debug.log`
- **Format:** `[YYYY-MM-DD HH:MM:SS.mmm] [ÇAĞIRAN_FONKSİYON] [SEVİYE] Mesaj`
- **Decorator `@timed_log`:** Fonksiyon girişinde `Called`, çıkışında `Completed in X.XXs`
- **Chunk snippet:** İlk 200 karakter loglanır

---

## 2. `ingestion_engine.py` — Chunk Detayları + Callback

- `_balanced_graph_ingest`, `process_file`, `_get_file_hash` → `@timed_log` ile sarılır
- **Birleşik progress:** `process_file` metoduna `progress_callback(file_index, file_total, chunk_index, chunk_total, filename)` parametresi eklenir
- **Log snippet örneği:**
  ```
  [2025-05-17 14:32:01.123] [_balanced_graph_ingest] DEBUG Chunk 3/8 snippet: "Metnin bu bölümündeki temel kavramlar..."
  ```

---

## 3. `search_engine.py` — Arama Logları

- `search` ve `add_to_index` süreleri loglanır
- Bulunan hit sayısı, sorgu metni loglanır

---

## 4. `llm_utils.py` — Üretim Logları

- `generate` ve `_stream_generate` başlangıç/bitiş loglanır
- Streaming sırasında token üretim adımları DEBUG olarak loglanır

---

## 5. `app.py` — Tek Bar + Adım Gösterimi

- **Mevcut bar korunur, birleşik mesaj:**  
  `Dosya 2/5: rapor.pdf | Chunk 3/8 | Zengin Analiz...`
- **Chat/LLM stream:** `st.status` ile adım gösterimi eklenir  
  `LLM yanıt üretimi: 1/3 adım...`