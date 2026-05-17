# 🧠 QwenRaggity V2: The Ultimate GraphRAG Engine

QwenRaggity V2, Microsoft'un **GraphRAG** zekası ile **LLM Wiki**'nin kalıcı bilgi tabanı mantığını birleştiren, **Qwen2.5-14B** tabanlı gelişmiş bir RAG (Retrieval-Augmented Generation) sistemidir.

## 🚀 Özellikler
- **GraphRAG Entegrasyonu:** Metinlerden otomatik olarak varlık (Entity) ve ilişki (Relationship) çıkarımı yapar.
- **Hibrit Arama:** Vektör benzerliği (LanceDB) ile Graf ilişkilerini birleştirerek daha zekice cevaplar verir.
- **Enterprise UI:** Gelişmiş Streamlit arayüzü ve akıllı PDF vurgulama (Highlighting) sistemi.
- **2-Step Ingestion:** LLM Wiki tarzı "Analiz -> Üretim" aşamalı içerik işleme.
- **Local & Remote Support:** Vast.ai, RunPod veya yerel GPU'larda çalışacak şekilde optimize edilmiştir.

## 🛠️ Kurulum

### 1. Kütüphaneleri Yükleyin
```bash
pip install lancedb tantivy PyMuPDF streamlit torch transformers accelerate bitsandbytes rank_bm25 sentence-transformers docling streamlit-pdf-viewer networkx
```

### 2. Çalıştırın
```bash
python runner.py
```

## 📂 Dosya Yapısı
- `app.py`: Streamlit Arayüzü.
- `graph_engine.py`: NetworkX tabanlı Graf Motoru.
- `ingestion_engine.py`: PDF işleme ve Varlık çıkarma.
- `search_engine.py`: Hibrit arama mekanizması.
- `llm_utils.py`: Model ve Embedder yönetimi.

## ⚠️ Gereksinimler
- En az **16GB VRAM** (Qwen-14B 4-bit için).
- İnternet bağlantısı (Modellerin ilk kez indirilmesi için).
