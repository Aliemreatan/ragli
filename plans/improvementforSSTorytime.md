# SSTorytime İlişki Kalitesi İyileştirme Planı

## Mevcut Sorunlar

1. **Chunk sınırları** - 16K tokenlik parçalarda ilişkiler kopuyor
2. **LLM prompting** - Yeterli relation type guidance yok
3. **Temperature** - 0.1 + top_p=0.11 ile daha deterministic çıktı
4. **Overlap azlığı** - 200 token ilişki trafiğini yakalamak için yetersiz
5. **Bağımsız chunk işleme** - Cross-chunk ilişkiler çıkarılamıyor
6. **Entity deduplication yok** - Aynı varlık farklı isimlerle birden fazla node oluşturuyor
7. **Relation type standardizasyonu eksik** - "kullanır", "kullanıyor", "kullanılmaktadır" ayrı arrow olarak kaydediliyor

---

## 1. Chunk Sınırları - Context Carryover

**Hedef:** Chunk geçişlerinde ilişki kopukluğunu önlemek

**Çözüm:** Her chunk'a önceki chunk'tan "carryover context" ekle

**Dosya:** `ingestion_engine.py`

**Implementasyon:**
```python
def _create_chunks_with_context(self, text, chunk_size=12000, overlap=2000):
    sentences = self._split_into_sentences(text)
    chunks = []
    for i in range(0, len(sentences), chunk_size - overlap):
        chunk_sentences = sentences[i:i + chunk_size]
        if i > 0 and chunks:
            prev_entities = self._extract_entity_names_from_chunk(chunks[-1])
            if prev_entities:
                context_header = f"[Önceki chunk'tan varlıklar: {', '.join(prev_entities)}]\n"
                chunk_sentences = [context_header] + chunk_sentences
        chunks.append(' '.join(chunk_sentences))
    return chunks
```

---

## 2. Relation Types - Pydantic Enum

**Hedef:** LLM'in rastgele relation type üretmesini engellemek

**Çözüm:** Pydantic model ile JSON çıktısını validate et ve relation type'ları enum ile sınırla

**Dosya:** `ingestion_engine.py` veya yeni `models.py`

**Implementasyon:**
```python
from pydantic import BaseModel, Field
from typing import Literal

class Entity(BaseModel):
    name: str
    type: Literal["Kişi", "Kurum", "Teknik Kavram", "Olay", "Yer", "Ürün", "Belge"]
    desc: str = ""

class Relationship(BaseModel):
    source: str
    target: str
    type: Literal["causes", "belongs_to", "located_in", "uses", "produces", "part_of", "related_to"]
    weight: float = Field(ge=0.0, le=2.0, default=1.0)

class ExtractionResult(BaseModel):
    entities: list[Entity]
    relationships: list[Relationship]
```

**LLM Promptu:**
```
Relation type'ları SADECE şunlardan biri olmalı:
- causes: Nedensellik
- belongs_to: Ait olma
- located_in: Bulunma
- uses: Kullanma
- produces: Üretme
- part_of: Parçası olma
- related_to: Genel ilişki
```

---

## 3. Temperature + Overlap Artırma

**Hedef:** Daha deterministic ve kapsamlı çıktı

**Dosya:** `ingestion_engine.py` (satır 65-66)

**Değişiklikler:**
```python
chunk_size = 12000    # 16000 yerine
overlap = 2000        # 200 yerine (10x artış)
```

**LLM çağrısı:**
```python
raw_res = llm.generate(
    [...],
    temperature=0.1,
    top_p=0.11         # Yeni: deterministic sampling
)
```

---

## 4. Sentence-Aware Chunking

**Hedef:** Cümle sınırlarından bölerek ilişki kopukluğunu önlemek

**Dosya:** `ingestion_engine.py`

**Implementasyon:**
```python
import re

def _split_into_sentences(self, text: str) -> list[str]:
    sentence_endings = r'(?<=[.!?])\s+'
    sentences = re.split(sentence_endings, text)
    return [s.strip() for s in sentences if s.strip()]

def _sentence_aware_chunk(self, text: str, target_tokens=12000, overlap_sentences=5):
    sentences = self._split_into_sentences(text)
    chunks = []
    current_chunk = []
    current_tokens = 0

    for i, sentence in enumerate(sentences):
        sentence_tokens = len(sentence.split())
        if current_tokens + sentence_tokens > target_tokens and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = current_chunk[-overlap_sentences:]
            current_tokens = sum(len(s.split()) for s in current_chunk)
        current_chunk.append(sentence)
        current_tokens += sentence_tokens

    if current_chunk:
        chunks.append(' '.join(current_chunk))
    return chunks
```

---

## 5. Cross-Chunk Graph Merge (İki-Pass Yaklaşım)

**Hedef:** Chunk'lar arası ilişkileri yakalamak

**Dosya:** `ingestion_engine.py`

**Implementasyon:**
```python
def _two_pass_extraction(self, text, filename, graph_engine=None):
    # Pass 1: Tüm entity'leri topla (ilişkisiz)
    all_entities = []
    chunks = self._sentence_aware_chunk(text)

    for i, chunk in enumerate(chunks[:8]):
        # Entity extraction only
        prompt = f"Tek tek tüm varlıkları çıkar, ilişkilendirme yapma:\n{chunk}"
        # Parse entities, store in all_entities

    # Pass 2: Tüm entity'ler arasında ilişki kur
    if all_entities and len(all_entities) > 1:
        entity_list = ', '.join([e['name'] for e in all_entities[:50]])
        relation_prompt = f"Şu varlıklar arasındaki ilişkileri çıkar:\n{entity_list}\n\nMetin:\n{text}"
        # Parse relationships

    # Sonuçları graph_engine'e ekle
```

**Risk:** Çok büyük PDF'lerde context penceresi aşılabilir. Limit: max 50 entity pass 2'de.

---

## 6. Entity Deduplication (Semantic Matching)

**Hedef:** Aynı varlığın farklı isimlerle birden fazla kez eklenmesini önlemek

**Dosya:** `ingestion_engine.py`

**Implementasyon:**
```python
def _deduplicate_entities(self, entities: list[dict], threshold=0.85) -> list[dict]:
    if not entities:
        return []

    embedder = get_embedder()
    names = [e['name'] for e in entities]
    embeddings = embedder.encode(names)

    from sklearn.metrics.pairwise import cosine_similarity
    similarity_matrix = cosine_similarity(embeddings)

    merged = {}
    for i, entity in enumerate(entities):
        canonical = entity['name']
        for j in range(i):
            if similarity_matrix[i][j] > threshold:
                # Merge i into j
                canonical = entities[j]['name']
                break
        if canonical not in merged:
            merged[canonical] = entity
        else:
            # Keep longer description
            if len(entity.get('desc', '')) > len(merged[canonical].get('desc', '')):
                merged[canonical] = entity

    return list(merged.values())
```

**Kullanım:** `_balanced_graph_ingest` sonunda tüm entity'leri deduplicate et.

---

## 7. Relation Type Clustering — Embedding-Based Hybrid

**Hedef:** Relation type'ları embeddings ile otomatik kümeleme ve normalize etme

**Kullanılan Modeller:**
- BGE Embedder (bi-encoder) — hızlı ilk taramada
- RERANKER (cross-encoder) — borderline case'ler için
- LLM — tie-breaker ve transitive validation

**Processing Timing:** Her chunk tamamlandıktan sonra (incremental, not batch)

**Dosya:** `ingestion_engine.py`

**Algoritma:**
```
Step A: BGE Embedding (First Pass)
    ↓
Raw Relation Types extracted (e.g., "kullanır", "kullandı", "üretti")
    ↓
Tüm unique type'lar embed edilir
Cosine similarity matrix hesaplanır
    ↓
Hard Cluster (similarity > 0.90) → kesin eşleşme, doğrudan aynı cluster
Soft Cluster (0.75 ≤ similarity ≤ 0.90) → reranker'a gönder
No Match (similarity < 0.75) → ayrı cluster olarak kalır
    ↓
Step B: Reranker (Second Pass)
    ↓
Borderline çiftler için cross-encoder kararı
Output: binary "same or not" + confidence score
    ↓
Step C: Conflict Resolution
    ↓
BGE ve Reranker skorları çakışırsa:
→ average_score = (BGE_similarity + reranker_score) / 2
→ average >= 0.85 → same cluster
→ average < 0.85 → LLM tie-breaker'a gönder
    ↓
Step D: LLM Tie-Breaker
    ↓
Prompt: "Bu iki ilişki türü aynı anlama mı geliyor? Sadece 'Evet' veya 'Hayır' cevap ver."
    ↓
Step E: Transitive Cluster Validation
    ↓
Eğer A≈B ve B≈C ama A≉C ise:
→ LLM'e tüm cluster'ı ver: "Bu relation type'lar aynı cluster'da olmalı mı?"
→ LLM transitive validation yapar
→ Onay alınırsa tek cluster, reddedilirse küçük cluster'lara bölünür
    ↓
Step F: Canonical Selection
    ↓
Her cluster'dan en sık görülen type → "canonical" seçilir
Cluster içindeki tüm original type'lar saklanır (metadata)
```

**Thresholds:**
| Parametre | Değer | Açıklama |
|-----------|-------|----------|
| hard_cluster | 0.90 | BGE'de >0.90 → otomatik aynı cluster |
| soft_min | 0.75 | BGE'de <0.75 → ayrı cluster |
| reranker_threshold | 0.75-0.90 | Reranker'a gönderilen aralık |
| final_avg | 0.85 | Ortalama skor >= 0.85 → aynı cluster |
| transitive_llm | — | LLM validation step |

**Örnek Akış:**

| Type A | Type B | BGE | Reranker | Avg | Karar |
|--------|--------|-----|----------|-----|-------|
| "kullanır" | "kullandı" | 0.92 | — | — | Same (hard) |
| "üretir" | "üretti" | 0.88 | 0.82 | 0.85 | Same (avg ≥ 0.85) |
| "parçasıdır" | "içinde" | 0.78 | 0.72 | 0.75 | LLM tie-breaker |
| A≈B, B≈C, A≉C | — | — | — | — | LLM transitive validation |

**Metadata Saklama:**
Her relation edge için:
```python
{
    "source": "A",
    "target": "B", 
    "type": "uses",  # canonical
    "original_type": "kullanılmaktadır",  # LLM'den gelen orijinal
    "cluster_id": "cluster_uses_001"
}
```

**Implementasyon:**
```python
from sklearn.metrics.pairwise import cosine_similarity

class RelationClusterer:
    def __init__(self, embedder, reranker, llm):
        self.embedder = embedder
        self.reranker = reranker
        self.llm = llm
        self.clusters = {}  # canonical_type -> {members: [], original_types: []}
        self.embedder_cache = {}

    def cluster_relation_types(self, new_types: list[str]):
        if not new_types:
            return {}

        # Step A: BGE embeddings
        embeddings = self.embedder.encode(new_types)
        similarity_matrix = cosine_similarity(embeddings)

        # Step B-E: Clustering logic
        for i, type_a in enumerate(new_types):
            for j, type_b in enumerate(new_types[i+1:], i+1):
                sim_bge = similarity_matrix[i][j]

                if sim_bge > 0.90:
                    self._merge_clusters(type_a, type_b)
                elif 0.75 <= sim_bge <= 0.90:
                    # Step B: Reranker
                    reranker_score = self._rerank(type_a, type_b)
                    avg_score = (sim_bge + reranker_score) / 2

                    if avg_score >= 0.85:
                        self._merge_clusters(type_a, type_b)
                    else:
                        # Step D: LLM tie-breaker
                        if self._llm_tiebreaker(type_a, type_b):
                            self._merge_clusters(type_a, type_b)
                # else: ayrı cluster, dokunma

        # Step E: Transitive validation
        self._validate_transitive_clusters()
        
        return self.get_canonical_mapping()

    def _llm_tiebreaker(self, type_a, type_b) -> bool:
        prompt = f"Bu iki ilişki türü aynı anlama mı geliyor? Sadece 'Evet' veya 'Hayır' cevap ver.\n1: {type_a}\n2: {type_b}"
        response = self.llm.generate([{"role": "user", "content": prompt}])
        return "evet" in response.lower()[:3]

    def _validate_transitive_clusters(self):
        for cluster in self.clusters.values():
            members = cluster["members"]
            for i, a in enumerate(members):
                for k, c in enumerate(members[i+2:], i+2):
                    if a not in cluster or c not in cluster:
                        continue
                    # A≈C kontrolü gerekiyor ama yok
                    if not self._are_same_cluster(a, c):
                        # Transitivity violated - LLM validate
                        if not self._llm_transitive_check(members):
                            self._split_cluster(cluster)

---

## Özet Tablo

| # | Sorun | Çözüm | Dosya | Risk |
|---|-------|-------|-------|------|
| 1 | Chunk sınırları | Context carryover | ingestion_engine.py | Düşük |
| 2 | LLM prompting | Pydantic enum | ingestion_engine.py | Düşük |
| 3 | Temperature/overlap | top_p=0.11, overlap=2000 | ingestion_engine.py | Düşük |
| 4 | Cümle kırılması | Sentence-aware chunking | ingestion_engine.py | Orta |
| 5 | Cross-chunk | Two-pass extraction | ingestion_engine.py | Yüksek (context) |
| 6 | Deduplication | Embedding similarity | ingestion_engine.py | Orta (performans) |
| 7 | Arrow standardizasyonu | BGE+Reranker+LLM hybrid + transitive validation | ingestion_engine.py | Orta (LLM maliyeti) |

---

## Yeni: Metadata Saklama

Relation edge'ler artık canonical type + original type saklar:
```python
edge("A", "B", uses, 1.0, original="kullanılmaktadır", cluster_id="cluster_uses_001")
```

Bu sayede:
- Graf sorguları canonical type ile yapılır
- Debugging için original type görülebilir
- Cluster membership takip edilebilir

1. **6 (Deduplication)** - Hemen etki, en hızlı kazanç
2. **3+4 (Overlap + Sentence-aware)** - Chunk kalitesini artırır
3. **2 (Pydantic enum)** - Tutarlı relation type üretimi
4. **7 (BGE+Reranker clustering)** - Tutarlı arrow type, incremental
5. **1 (Context carryover)** - Chunk geçişlerini iyileştir
6. **5 (Two-pass)** - En büyük etki, en yüksek risk

---

## Test Etme

Her değişiklikten sonra:
1. Aynı PDF'i işle
2. Graph'deki node/edge sayısını karşılaştır
3. Beklenen: Daha az node, daha fazla edge, daha tutarlı relation type'lar