# Logging + Progress Bar Ekleme Planı

## Durum: ✅ TAMAMLANDI

## Tamamlanan Değişiklikler

### 1. `logger_config.py` — Merkezi Logger (Oluşturuldu)
- **Çıktı dosyası:** `logs/debug.log`
- **Format:** `[YYYY-MM-DD HH:MM:SS] [FONKSİYON] [SEVİYE] Mesaj`
- **Decorator `@timed_log`:** Fonksiyon girişinde `Called`, çıkışında `Completed in X.XXs`
- **Chunk snippet:** İlk 200 karakter loglanır

### 2. `ingestion_engine.py` — Chunk Detayları + Callback
- `_get_file_hash`, `process_file`, `_balanced_graph_ingest` → `@timed_log` ile süslendi
- `progress_callback(file_idx, file_total, chunk_idx, chunk_total, filename)` parametresi eklendi
- Tüm `print()` çağrıları `logger.info/error` ile değiştirildi

### 3. `search_engine.py` — Arama Logları
- `add_to_index` ve `search` → `@timed_log` ile süslendi
- Sorgu metni ve chunk sayısı loglanıyor

### 4. `llm_utils.py` — Üretim Logları
- `generate` ve `_stream_generate` → `@timed_log` ile süslendi
- Model yükleme mesajları logger'a yönlendirildi

### 5. `app.py` — Tek Bar + Adım Gösterimi
- **Birleşik progress callback:** Hem dosya hem chunk ilerlemesi gösteriliyor
- **Mesaj format:** `Dosya 2/5: rapor.pdf | Chunk 3/8`
- `progress_callback` lambda ile doğru file/chunk bilgisi aktarılıyor