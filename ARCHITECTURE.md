# QwenRaggity V2: The Ultimate Knowledge Engine

Bu proje, orijinal **QwenRaggity** mimarisini alarak, sektör standartlarını belirleyen iki devrimsel yaklaşımı (**GraphRAG** ve **LLM Wiki**) tek bir birleşik sistemde harmanlar.

## 🚀 Yeni Mimari Vizyonu

Yeni sistem, bilgi çıkarımından kullanıcı arayüzüne kadar 4 ana motor üzerine inşa edilmiştir:

### 1. Ingestion Engine (Veri Alma Motoru)
**LLM Wiki**'nin 2 aşamalı (Analysis & Generation) veri alım stratejisini kullanırken, **GraphRAG**'in Varlık/İlişki (Entity/Relationship) çıkarımını da işin içine katar.
- **Two-Step Chain-of-Thought:** İlk adımda LLM dokümanı analiz eder, ikinci adımda bilgi ağacı formatında markdown (Obsidian uyumlu) çıktı ve metadata (YAML) üretir.
- **Multimodal (Çoklu Mod):** PDF içindeki görseller çıkarılır, Vision modeli ile açıklama (caption) yazılır ve aranabilir hale getirilir.
- **Auto-Watch & Queue:** Klasöre atılan belgeler otomatik izlenir, bir kuyruğa alınır ve sırayla indekslenir (SHA256 hash ile sadece değişenler güncellenir).

### 2. Graph Engine (Bilgi Grafiği Motoru)
**GraphRAG** ve **LLM Wiki** yeteneklerinin mükemmel kesişimi.
- **Leiden & Louvain Kümelemesi:** Çıkarılan varlıklar (entities) hiyerarşik olarak kümelenir.
- **4-Signal Relevance Model:** Düğümler (Nodes) arası bağlar doğrudan referans, kaynak örtüşmesi, Adamic-Adar ve tip benzerliğine göre hesaplanır.
- **Community Summaries:** Her küme (topluluk) için aşağıdan yukarıya doğru otomatik özetler çıkarılır (GraphRAG yaklaşımı).

### 3. Search Engine (Arama ve Çıkarım Motoru)
Kullanıcının amacına göre otomatik mod seçimi.
- **Global Search:** Bütünsel "Büyük resim nedir?" soruları için Community Summary'leri üzerinden arama.
- **Local Search:** Spesifik varlıklar ve onlara bağlı düğümler etrafında derinlemesine arama.
- **DRIFT Search:** Yerel bir aramayı topluluk (community) bağlamıyla birleştirerek genişleten arama.
- **Hybrid Semantic Search:** FAISS + BM25 + Cross-Encoder reranking (QwenRaggity'nin orijinal güçlü vektör araması korunmuştur).
- **Deep Research:** Eğer grafikte eksik bir bilgi varsa, "Tavily" veya "SearXNG" gibi araçlarla web'de derin araştırma başlatılır ve bulgular grafiğe eklenir.

### 4. UI & Interaction (Arayüz Motoru)
Streamlit üzerinde 3 sütunlu profesyonel görünüm.
- **Sol Panel:** Bilgi Ağacı (Knowledge Tree) ve Kuyruk Yönetimi.
- **Orta Panel:** Chat & Graph Insights (Grafik görselleştirme entegrasyonu).
- **Sağ Panel:** PDF Viewer ve Bağlam Görüntüleyici (Orijinal QwenRaggity yeteneği, PDF üzerinde sarı işaretleme).

## 📂 Dosya Yapısı

- `app.py`: Ana Streamlit arayüzü ve orkestrasyon.
- `ingestion_engine.py`: Dosya okuma (Docling), 2 aşamalı LLM işleme ve Multimodal işlemler.
- `graph_engine.py`: NetworkX tabanlı grafik inşası, Leiden algoritmaları ve Topluluk özetleri.
- `search_engine.py`: Global, Local, DRIFT ve Hybrid vektör arama yönlendiricisi.
- `llm_utils.py`: Ollama, Embedder ve Reranker servis sarmalayıcıları (wrappers).
