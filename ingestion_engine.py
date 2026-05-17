# -*- coding: utf-8 -*-
import os
import hashlib
import json
import re
import fitz
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field
from collections import Counter

from llm_utils import get_llm, get_embedder, get_reranker
from logger_config import logger, timed_log


class EntityModel(BaseModel):
    name: str
    type: Literal["Kişi", "Kurum", "Teknik Kavram", "Olay", "Yer", "Ürün", "Belge"]
    desc: str = ""


class RelationshipModel(BaseModel):
    source: str
    target: str
    type: str
    weight: float = Field(ge=0.0, le=2.0, default=1.0)
    original_type: Optional[str] = None
    cluster_id: Optional[str] = None


class ExtractionResult(BaseModel):
    entities: list[EntityModel]
    relationships: list[RelationshipModel]


class RelationClusterer:
    THRESHOLDS = {
        "hard_cluster": 0.90,
        "soft_min": 0.75,
        "final_avg": 0.85
    }

    def __init__(self):
        self._embedder = None
        self._reranker = None
        self._llm = None
        self.clusters = {}  # canonical -> {"members": [], "originals": []}
        self.type_to_cluster = {}  # original_type -> canonical

    @property
    def embedder(self):
        if self._embedder is None:
            from llm_utils import get_embedder, reload_embedder_reranker
            reload_embedder_reranker()
            self._embedder = get_embedder()
        return self._embedder

    @property
    def reranker(self):
        if self._reranker is None:
            from llm_utils import get_reranker
            self._reranker = get_reranker()
        return self._reranker

    @property
    def llm(self):
        if self._llm is None:
            from llm_utils import get_llm
            self._llm = get_llm()
        return self._llm

    def cluster_types(self, new_types: list[str]):
        if not new_types:
            return {}

        embeddings = self.embedder.encode(new_types)
        from sklearn.metrics.pairwise import cosine_similarity
        sim_matrix = cosine_similarity(embeddings)

        for i, type_a in enumerate(new_types):
            for j, type_b in enumerate(new_types[i+1:], i+1):
                sim_bge = sim_matrix[i][j]

                if sim_bge > self.THRESHOLDS["hard_cluster"]:
                    self._merge_clusters(type_a, type_b)
                elif self.THRESHOLDS["soft_min"] <= sim_bge <= self.THRESHOLDS["hard_cluster"]:
                    reranker_score = self._rerank(type_a, type_b)
                    avg_score = (sim_bge + reranker_score) / 2

                    if avg_score >= self.THRESHOLDS["final_avg"]:
                        self._merge_clusters(type_a, type_b)
                    else:
                        if self._llm_tiebreaker(type_a, type_b):
                            self._merge_clusters(type_a, type_b)

        self._validate_transitive_clusters()
        return self.get_canonical_mapping()

    def _rerank(self, type_a: str, type_b: str) -> float:
        pair = [[type_a, type_b]]
        scores = self.reranker.predict(pair)
        return float(scores[0])

    def _llm_tiebreaker(self, type_a: str, type_b: str) -> bool:
        prompt = f"Bu iki ilişki türü aynı anlama mı geliyor? Sadece 'Evet' veya 'Hayır' cevap ver.\n1: {type_a}\n2: {type_b}"
        response = self.llm.generate([{"role": "user", "content": prompt}])
        return "evet" in response.lower()[:3]

    def _llm_transitive_check(self, cluster_members: list[str]) -> bool:
        types_str = "\n".join([f"- {t}" for t in cluster_members])
        prompt = f"Bu relation type'lar aynı cluster'da olmalı mı? Liste:\n{types_str}\n\nTümü aynı anlama mı geliyor? 'Evet' veya 'Hayır' cevap ver."
        response = self.llm.generate([{"role": "user", "content": prompt}])
        return "evet" in response.lower()[:3]

    def _merge_clusters(self, type_a: str, type_b: str):
        cluster_a = self.type_to_cluster.get(type_a)
        cluster_b = self.type_to_cluster.get(type_b)

        if cluster_a and cluster_b:
            if cluster_a != cluster_b:
                merged_members = self.clusters[cluster_a]["members"] + self.clusters[cluster_b]["members"]
                merged_originals = self.clusters[cluster_a]["originals"] + self.clusters[cluster_b]["originals"]
                del self.clusters[cluster_a]
                del self.clusters[cluster_b]
                canonical = cluster_a
                self.clusters[canonical] = {"members": merged_members, "originals": merged_originals}
                for t in merged_members:
                    self.type_to_cluster[t] = canonical
        elif cluster_a:
            self.clusters[cluster_a]["members"].append(type_b)
            self.clusters[cluster_a]["originals"].append(type_b)
            self.type_to_cluster[type_b] = cluster_a
        elif cluster_b:
            self.clusters[cluster_b]["members"].append(type_a)
            self.clusters[cluster_b]["originals"].append(type_a)
            self.type_to_cluster[type_a] = cluster_b
        else:
            canonical = type_a
            self.clusters[canonical] = {"members": [type_a, type_b], "originals": [type_a, type_b]}
            self.type_to_cluster[type_a] = canonical
            self.type_to_cluster[type_b] = canonical

    def _validate_transitive_clusters(self):
        for canonical, cluster in list(self.clusters.items()):
            members = cluster["members"]
            to_remove = []

            for i, a in enumerate(members):
                for k, c in enumerate(members[i+2:], i+2):
                    if a not in self.type_to_cluster or c not in self.type_to_cluster:
                        continue
                    if self.type_to_cluster[a] != self.type_to_cluster[c]:
                        if not self._llm_transitive_check(members):
                            to_remove = members.copy()
                            break

            if to_remove:
                del self.clusters[canonical]
                for t in to_remove:
                    if t in self.type_to_cluster:
                        del self.type_to_cluster[t]
                for t in to_remove:
                    self.clusters[t] = {"members": [t], "originals": [t]}
                    self.type_to_cluster[t] = t

    def get_canonical_mapping(self) -> dict:
        mapping = {}
        for original, canonical in self.type_to_cluster.items():
            if original != canonical:
                mapping[original] = canonical
        return mapping

    def get_canonical(self, original_type: str) -> str:
        return self.type_to_cluster.get(original_type, original_type)


class N4LTranslator:
    ARROW_TYPES = {"causality": "->", "containment": ">>", "similarity": "<->", "expression": "~>"}

    @staticmethod
    def json_to_n4l(data, filename):
        lines = []
        lines.append(f"# N4L file for {filename}")
        lines.append(f"# Generated: {datetime.now().isoformat()}")
        lines.append("")

        for ent in data.get("entities", []):
            vtype = ent.get("type", "unknown").lower()
            if vtype == "kişi":
                vtype = "person"
            elif vtype == "kurum":
                vtype = "organization"
            elif vtype == "teknik kavram":
                vtype = "concept"
            elif vtype == "olay":
                vtype = "event"
            lines.append(f'vertex("{ent["name"]}", {vtype})')

        lines.append("")
        for rel in data.get("relationships", []):
            arrow = rel.get("type", "related_to")
            weight = rel.get("weight", 1.0)
            lines.append(f'edge("{rel["source"]}", "{rel["target"]}", {arrow}, {weight})')

        return "\n".join(lines)


class TwoStepIngestor:
    def __init__(self, workspace_dir="workspace"):
        self.workspace_dir = workspace_dir
        self.raw_dir = os.path.join(workspace_dir, "raw")
        self.wiki_dir = os.path.join(workspace_dir, "wiki")
        self.relation_clusterer = RelationClusterer()

        for d in [self.raw_dir, self.wiki_dir]:
            if not os.path.exists(d):
                os.makedirs(d)

    def _split_into_sentences(self, text: str) -> list[str]:
        sentence_endings = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_endings, text)
        return [s.strip() for s in sentences if s.strip()]

    def _sentence_aware_chunk(self, text: str, target_tokens: int = 12000, overlap_sentences: int = 5) -> list[str]:
        sentences = self._split_into_sentences(text)
        chunks = []
        current_chunk = []
        current_tokens = 0

        for sentence in sentences:
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

    def _deduplicate_entities(self, entities: list[dict], threshold: float = 0.85) -> list[dict]:
        if not entities:
            return []

        from llm_utils import get_embedder, reload_embedder_reranker
        reload_embedder_reranker()
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
                    canonical = entities[j]['name']
                    break
            if canonical not in merged:
                merged[canonical] = entity.copy()
            else:
                if len(entity.get('desc', '')) > len(merged[canonical].get('desc', '')):
                    merged[canonical] = entity.copy()

        return list(merged.values())

    def _carryover_context(self, previous_chunk: str, max_tokens: int = 200) -> str:
        sentences = self._split_into_sentences(previous_chunk)
        if len(sentences) <= 3:
            return ""

        carried = sentences[-3:]
        context = "[Önceki chunk'tan relevant bilgiler: " + ' '.join(carried) + "]"
        if len(context.split()) > max_tokens:
            context = "[Önceki chunk'tan relevant bilgiler: " + ' '.join(carried[:2]) + "]"

        return context

    @timed_log
    def _get_file_hash(self, filepath):
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    @timed_log
    def process_file(self, filepath, graph_engine=None, progress_callback=None):
        file_hash = self._get_file_hash(filepath)
        filename = os.path.basename(filepath)

        cache_path = os.path.join(self.raw_dir, f"{filename}.meta.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r") as f:
                meta = json.load(f)
                if meta.get("hash") == file_hash:
                    logger.info(f"[{filename}] Cache Hit - Atlanıyor.")
                    return None

        logger.info(f"[{filename}] Okunuyor...")
        try:
            doc = fitz.open(filepath)
            full_text = ""
            for page in doc:
                full_text += page.get_text() + "\n"
            doc.close()
        except Exception as e:
            logger.error(f"[{filename}] Hata: {e}")
            return None

        with open(os.path.join(self.raw_dir, f"{filename}.md"), "w", encoding="utf-8") as f:
            f.write(full_text)

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"hash": file_hash, "processed_at": str(datetime.now())}, f)

        return self._balanced_graph_ingest(full_text, filename, graph_engine)

    @timed_log
    def _balanced_graph_ingest(self, text, filename, graph_engine=None):
        llm = get_llm()

        chunk_size = 12000
        overlap = 2000

        chunks = self._sentence_aware_chunk(text, target_tokens=chunk_size, overlap_sentences=5)
        all_entities = []
        all_relations = []

        logger.info(f"[{filename}] {len(chunks)} büyük parça üzerinde Zengin Analiz başlatılıyor...")

        for i, chunk in enumerate(chunks):
            if i > 7:
                break

            if i > 0:
                context = self._carryover_context(chunks[i-1])
                if context:
                    chunk = context + "\n" + chunk

            logger.info(f"[{filename}] Chunk {i+1}/{min(len(chunks), 8)} işleniyor...")

            snippet = chunk[:200].replace("\n", " ")
            logger.debug(f"Chunk {i+1} snippet: \"{snippet}...\"")

            prompt = f"""
Metni derinlemesine analiz et. Tüm varlıkları (Entity) ve ilişkileri (Relationship) çıkar.
Çıktıyı MUTLAKA sadece şu JSON formatında ver:
{{
  "entities": [
    {{ "name": "Varlık Adı", "type": "Kişi/Kurum/Teknik Kavram/Olay", "desc": "Detaylı açıklama" }}
  ],
  "relationships": [
    {{ "source": "Varlık A", "target": "Varlık B", "type": "İlişki Türü", "weight": 1.5 }}
  ]
}}

Relation type'ları SADECE şunlardan biri olmalı:
- causes: Nedensellik ifade eden
- belongs_to: Ait olma, parçası olma
- located_in: Yerde bulunma
- uses: Kullanma, tüketme
- produces: Üretme, yaratma
- part_of: Parçası olma
- related_to: Genel ilişki

METİN PARÇASI:
{chunk}
"""
            raw_res = llm.generate([{"role": "user", "content": prompt}], temperature=0.1, top_p=0.11, max_new_tokens=2048)

            try:
                json_match = re.search(r'\{.*\}', raw_res.replace('\n', ' '), re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                        chunk_entities = data.get('entities', [])
                        chunk_relations = data.get('relationships', [])

                        if not chunk_entities and not chunk_relations:
                            logger.warning(f"[{filename}] Chunk {i+1}: Boş entity/relation listesi döndü")

                        logger.info(f"[{filename}] Chunk {i+1}: {len(chunk_entities)} entities, {len(chunk_relations)} relations")

                        all_entities.extend(chunk_entities)

                        raw_types = [r.get('type', 'related_to') for r in chunk_relations]
                        canonical_mapping = self.relation_clusterer.cluster_types(raw_types)

                        for rel in chunk_relations:
                            rel_type = rel.get('type', 'related_to')
                            canonical = canonical_mapping.get(rel_type, rel_type)
                            rel['type'] = canonical
                            rel['original_type'] = rel_type

                        all_relations.extend(chunk_relations)

                        if graph_engine:
                            for ent in chunk_entities:
                                graph_engine.add_entity(ent['name'], ent['type'], {'desc': ent.get('desc', '')})
                            for rel in chunk_relations:
                                graph_engine.add_relationship(rel['source'], rel['target'], rel['type'], rel.get('weight', 1.0))

                        n4l_content = N4LTranslator.json_to_n4l({"entities": chunk_entities, "relationships": chunk_relations}, filename)
                        n4l_path = os.path.join(self.workspace_dir, "n4l", f"{filename}_chunk{i}.in")
                        os.makedirs(os.path.dirname(n4l_path), exist_ok=True)
                        with open(n4l_path, 'w', encoding='utf-8') as f:
                            f.write(n4l_content)
                        logger.debug(f"N4L file written: {n4l_path}")

                    except Exception as e:
                        logger.error(f"[{filename}] JSON Ayrıştırma Sorunu (Parça {i+1}): {e}")

                else:
                    logger.error(f"[{filename}] Chunk {i+1}: JSON match bulunamadı. LLM response: {raw_res[:500]}")

            except Exception as e:
                logger.error(f"[{filename}] Chunk {i+1}: Genel hata: {e}")

            finally:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

        if all_entities and graph_engine:
            deduplicated = self._deduplicate_entities(all_entities)
            logger.info(f"[{filename}] Entity deduplication: {len(all_entities)} -> {len(deduplicated)}")

        if graph_engine:
            graph_engine.save()
            logger.info(f"[{filename}] Zengin Graf Başarıyla Güncellendi.")

        cross_chunk_relations = self._extract_cross_chunk_relations(all_entities, chunks, llm)
        if cross_chunk_relations and graph_engine:
            for rel in cross_chunk_relations:
                graph_engine.add_relationship(rel['source'], rel['target'], rel['type'], rel.get('weight', 1.0))
            logger.info(f"[{filename}] Cross-chunk ilişkileri eklendi: {len(cross_chunk_relations)}")

        return {"raw_text": text, "wiki": "Zengin Ingest Tamamlandı.", "stats": {
            "chunks": len(chunks),
            "entities": len(all_entities),
            "relations": len(all_relations),
            "cross_chunk_relations": len(cross_chunk_relations),
            "clusters": len(self.relation_clusterer.clusters)
        }}

    def _extract_cross_chunk_relations(self, all_entities: list[dict], chunks: list[str], llm) -> list[dict]:
        if len(all_entities) < 3 or len(chunks) < 2:
            return []

        entity_freq = Counter([e['name'] for e in all_entities])
        high_freq_entities = [e for e, count in entity_freq.items() if count >= 2]

        if len(high_freq_entities) < 2:
            return []

        high_freq_str = ", ".join(high_freq_entities[:30])

        prompt = f"""Şu varlıklar arasındaki TÜM ilişkileri çıkar. Bu varlıklar farklı chunk'larda görülmüş, aralarındaki cross-chunk ilişkilerini bul:

Varlıklar: {high_freq_str}

Mevcut ilişkiler (varsa):
{self._get_existing_relations_hint(chunks)}

Çıktı formatı (sadece JSON):
{{
  "relationships": [
    {{ "source": "Varlık A", "target": "Varlık B", "type": "İlişki Türü", "weight": 1.0 }}
  ]
}}
"""
        raw_res = llm.generate([{"role": "user", "content": prompt}], temperature=0.1, top_p=0.11, max_new_tokens=1024)

        json_match = re.search(r'\{.*\}', raw_res.replace('\n', ' '), re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                relations = data.get('relationships', [])
                for rel in relations:
                    rel_type = rel.get('type', 'related_to')
                    canonical = self.relation_clusterer.get_canonical(rel_type)
                    rel['type'] = canonical
                return relations
            except Exception as e:
                logger.error(f"Cross-chunk relation extraction error: {e}")

        return []

    def _get_existing_relations_hint(self, chunks: list[str]) -> str:
        sample = chunks[:3] if len(chunks) > 3 else chunks
        hint = []
        for i, c in enumerate(sample):
            entities_in_chunk = re.findall(r'"name":\s*"([^"]+)"', c)
            if entities_in_chunk:
                hint.append(f"Chunk {i+1}: {', '.join(entities_in_chunk[:5])}")
        return "\n".join(hint) if hint else "İlişki bulunamadı"