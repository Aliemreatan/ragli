# Bilgi Grafiği Görselleştirme ve Düğüm Yönetimi Planı

**Hedef:** KNRAG sisteminden çıkarılan varlıkları ve ilişkileri interaktif olarak görselleştirmek ve yönetmek.

---

## Durum: Tamamlanan Görevler

### Tamamlanan

**Görev 1: Streamlit Graf Görselleştirme**
- `app.py`'de tab yapısı: `tab1, tab2 = st.tabs(["💬 Sohbet", "🔍 Bilgi Grafiği"])`
- Düğüm tiplerine göre renk uygulaması (Kişi: mavi, Kurum: yeşil, vb.)
- Kenar weight'ine göre çizgi kalınlığı

**Görev 2: Community Detection**
- `graph_engine.py`'ye `detect_communities()` metodu eklendi
- Leiden algorithm ile topluluk tespiti
- `workspace/communities.json` olarak kaydetme

**Görev 3: İstatistik Panosu**
- 4 metrik kutusu: Düğümler, İlişkiler, Community'ler, Yoğunluk
- Varlık tipi dağılımı

**Görev 4: Düğüm Arama ve Filtreleme**
- Arama kutusu ile düğüm filtreleme
- Tip filtresi ile çoklu seçim

**Görev 5: Düğüm Detay Görünümü**
- Seçili düğümün detayları (tip, açıklama)
- Bağlı düğümler ve ilişki tipleri listesi

---

## Yeni Eklenen Kütüphaneler (requirements.txt)

```
streamlit-agraph>=0.0.45
python-igraph>=0.11
leidenalg>=0.10
plotly>=5.18
matplotlib>=3.8
```

---

## Yeni graph_engine.py Metotları

- `detect_communities()` - Leiden ile topluluk tespiti
- `get_stats()` - Graf istatistikleri
- `get_top_entities(n, metric)` - Merkezi düğümler
- `get_node_type_counts()` - Tip dağılımı
- `get_entity_by_type(type)` - Tip bazlı düğümler
- `search_entities(query, type)` - Arama

---

## Yapılacak (Planlanan ama henüz uygulanmamış)

- Community özetleri (LLM ile otomatik)
- Community görselleştirme modu (renk bazlı)
- Graf dışa aktarma (GraphML/Gephi)
- En çok bağlantılı düğümler listesi