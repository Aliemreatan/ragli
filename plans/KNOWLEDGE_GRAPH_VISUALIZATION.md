# 🧠 Knowledge Graph Visualization & Node Management Plan

**Hedef:** KNRAG sisteminden çıkarılan varlıkları (entities) ve ilişkileri (relationships) interaktif olarak görselleştirmek ve yönetmek.

**Yaklaşım:** Streamlit内置 interaktif graf + NetworkX + Community Detection

---

## 📋 Mevcut Durum

### Mevcut `graph_engine.py` Yetenekleri:
- ✅ `add_entity()` / `add_relationship()` - Düğüm/kenar ekleme
- ✅ `save()` / `load()` - JSON kaydetme/yükleme
- ✅ `get_entity_context()` - Komşu bağlamı
- ✅ `get_all_entities()` - Tüm düğümler

### Eksik:
- ❌ Interaktif graf görselleştirme
- ❌ Community detection (Leiden/Louvain)
- ❌ Düğüm filtreleme/arama
- ❌ İstatistik panosu
- ❌ Düğüm detay görünümü
- ❌ Community özetleri

---

## 🎯 8 Görev (Öncelik Sırasına Göre)

### Görev 1: Streamlit Graf Görselleştirme (Yüksek, 2-3 saat)
**Dosya:** `app.py` + yeni kütüphane: `streamlit-agraph`

- [ ] 1.1 `streamlit-agraph` kütüphanesini `requirements.txt`'e ekle
- [ ] 1.2 `app.py`'de tab yapısı oluştur: `tab1, tab2 = st.tabs(["💬 Sohbet", "🔍 Bilgi Grafiği"])`
- [ ] 1.3 Mevcut Chat+PDF layout'u tab1'e taşı
- [ ] 1.4 tab2'de `streamlit-agraph` ile interaktif graf oluştur
- [ ] 1.5 Düğüm tiplerine göre renk uygula:
  - `Kişi` → `#4285F4` (Mavi)
  - `Kurum` → `#34A853` (Yeşil)
  - `Teknik Kavram` → `#9C27B0` (Mor)
  - `Olay` → `#FF6D00` (Turuncu)
- [ ] 1.6 Kenar weight'ine göre çizgi kalınlığı uygula
- [ ] 1.7 Düğüme tıklayınca detay popup'ı göster

```python
from streamlit_agraph import agraph, Node, Edge, Config

TYPE_COLORS = {
    "Kişi": "#4285F4", "Kurum": "#34A853",
    "Teknik Kavram": "#9C27B0", "Olay": "#FF6D00",
    "Yer": "#00ACC1", "Ürün": "#FFD600", "Belge": "#78909C"
}

nodes = []
for entity_id in graph_engine.get_all_entities():
    node_data = graph_engine.graph.nodes[entity_id]
    nodes.append(Node(
        id=entity_id, label=entity_id, size=20,
        color=TYPE_COLORS.get(node_data.get('type', ''), '#888')
    ))

edges = []
for src, tgt, data in graph_engine.graph.edges(data=True):
    edges.append(Edge(source=src, target=tgt, label=data.get('type', '')))

config = Config(width=700, height=500, directed=False, physics=True)
agraph(nodes=nodes, edges=edges, config=config)
```

---

### Görev 2: Community Detection - Leiden (Yüksek, 1-2 saat)
**Dosya:** `graph_engine.py` (genişletme)

- [ ] 2.1 `python-igraph` ve `leidenalg` kütüphanelerini `requirements.txt`'e ekle
- [ ] 2.2 `detect_communities()` metodu ekle
- [ ] 2.3 Her community'ye renk ataması yap
- [ ] 2.4 Community'leri `workspace/communities.json` olarak kaydet
- [ ] 2.5 Her community'nin en merkezi düğümlerini listele

```python
import igraph as ig
import leidenalg

def detect_communities(self):
    if len(self.graph.nodes) < 2:
        return []
    
    ig_graph = ig.Graph.from_networkx(self.graph)
    partitions = leidenalg.find_partition(
        ig_graph, leidenalg.ModularityVertexPartition
    )
    
    communities = []
    COMMUNITY_PALETTE = [
        "#E91E63", "#9C27B0", "#673AB7", "#3F51B5",
        "#2196F3", "#00BCD4", "#4CAF50", "#FFC107"
    ]
    
    for i, community in enumerate(partitions):
        members = [ig_graph.vs[v]["_nx_name"] for v in community]
        communities.append({
            "id": i, "members": members,
            "size": len(members),
            "color": COMMUNITY_PALETTE[i % len(COMMUNITY_PALETTE)]
        })
    
    return communities
```

---

### Görev 3: İstatistik Panosu (Orta, 1 saat)
**Dosya:** `app.py` (graf sekmesinde)

- [ ] 3.1 4 metrik kutusu: Düğümler, İlişkiler, Community'ler, Yoğunluk
- [ ] 3.2 Düğüm tipi dağılımı (pasta grafik - plotly)
- [ ] 3.3 Community büyüklük dağılımı (çubuk grafik)
- [ ] 3.4 En çok bağlantılı 5 düğüm (degree centrality)

```python
col1, col2, col3, col4 = st.columns(4)
col1.metric("Düğümler", len(graph.nodes))
col2.metric("İlişkiler", len(graph.edges))
col3.metric("Community'ler", len(communities))
col4.metric("Yoğunluk", f"{nx.density(graph):.3f}")
```

---

### Görev 4: Düğüm Arama ve Filtreleme (Orta, 1-2 saat)
**Dosya:** `app.py`

- [ ] 4.1 Arama kutusu: `st.text_input("🔍 Düğüm ara...")`
- [ ] 4.2 Tip filtresi: `st.multiselect("Tip filtresi", [...])`
- [ ] 4.3 Community filtresi: `st.selectbox("Community", [...])`
- [ ] 4.4 Filtrelenmiş grafiı güncelle
- [ ] 4.5 Seçili düğümün 1-hop ve 2-hop komşularını vurgula

---

### Görev 5: Düğüm Detay Görünümü (Orta, 1 saat)
**Dosya:** `app.py`

- [ ] 5.1 Graf altında detay paneli göster
- [ ] 5.2 Düğüm adı, tipi, açıklaması
- [ ] 5.3 Bağlı düğümler ve ilişki tipleri listesi
- [ ] 5.4 Community bilgisi
- [ ] 5.5 "Bu düğüm hakkında soru sor" butonu → sohbet paneline bağlam gönder

---

### Görev 6: Community Özetleri (Düşük, 2-3 saat)
**Dosya:** `graph_engine.py` + `app.py`

- [ ] 6.1 Her community için LLM ile otomatik özet oluştur
- [ ] 6.2 Özetleri `workspace/community_summaries.json` olarak kaydet
- [ ] 6.3 Graf arayüzünde community'leri listele
- [ ] 6.4 Her community'nin en merkezi düğümlerini göster

---

### Görev 7: Community Görselleştirme Modu (Düşük, 1-2 saat)
**Dosya:** `app.py`

- [ ] 7.1 "Community Görünümü" toggle butonu
- [ ] 7.2 Aynı community'deki düğümler aynı renkte
- [ ] 7.3 Community'ler arası köprü düğümleri vurgula

---

### Görev 8: Graf Dışa Aktarma (Düşük, 1 saat)
**Dosya:** `graph_engine.py`

- [ ] 8.1 GraphML formatında dışa aktarma (Gephi uyumlu)
- [ ] 8.2 PNG/SVG olarak dışa aktarma
- [ ] 8.3 Community raporu dışa aktarma butonu

---

## 📊 Uygulama Sırası

| Sıra | Görev | Öncelik | Süre |
|------|-------|---------|------|
| 1 | Graf Görselleştirme | Yüksek | 2-3 saat |
| 2 | Community Detection | Yüksek | 1-2 saat |
| 3 | İstatistik Panosu | Orta | 1 saat |
| 4 | Arama & Filtreleme | Orta | 1-2 saat |
| 5 | Düğüm Detay | Orta | 1 saat |
| 6 | Community Özetleri | Düşük | 2-3 saat |
| 7 | Community Görselleştirme | Düşük | 1-2 saat |
| 8 | Graf Dışa Aktarma | Düşük | 1 saat |

**Toplam:** 10-15 saat

---

## 🔧 Gerekli Yeni Kütüphaneler

```
streamlit-agraph>=0.0.45
python-igraph>=0.11
leidenalg>=0.10
plotly>=5.18
matplotlib>=3.8
```

---

## 📐 `graph_engine.py` Yeni Metotlar

```python
# Mevcut metotlar korunacak, bunlar eklenecek:
def detect_communities(self) -> list: ...
def get_subgraph(self, entity_ids: list) -> nx.Graph: ...
def get_stats(self) -> dict: ...
def get_top_entities(self, n: int, metric: str) -> list: ...
def search_entities(self, query: str, entity_type: str = None) -> list: ...
def generate_community_summaries(self, llm) -> list: ...
def export_graphml(self, filepath: str): ...
def export_gexf(self, filepath: str): ...
```

---

## 📐 `app.py` UI Değişiklikleri

```python
# Mevcut: 2 sütun (Chat + PDF)
# Yeni: Sekmeli yapı
tab1, tab2 = st.tabs(["💬 Sohbet", "🔍 Bilgi Grafiği"])

# tab1: Mevcut Chat + PDF Viewer
# tab2: Graf görselleştirme + İstatistikler + Filtreler + Düğüm detay
```

---

## ✅ Test Planı

### Görev 1 Testi:
1. PDF yükle ve işle
2. Graf sekmesinde düğümlerin göründüğünü doğrula
3. Düğüm tiplerinin doğru renkte göründüğünü doğrula

### Görev 2 Testi:
1. `detect_communities()` metodunu çağır
2. Community sayısının > 0 olduğunu doğrula
3. `workspace/communities.json` dosyasının oluştuğunu doğrula

### Görev 3-5 Testi:
1. İstatistik panosunun doğru değerleri gösterdiğini doğrula
2. Arama kutusunun düğümleri filtrelediğini doğrula
3. Düğüm detay panelinin doğru bilgileri gösterdiğini doğrula

---

**Plan Versiyonu:** 1.0
**Oluşturulma Tarihi:** 2026-05-17
**Durum:** Planlama Aşaması - Uygulama Onayı Bekleniyor