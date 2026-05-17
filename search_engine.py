# -*- coding: utf-8 -*-
import lancedb
import pandas as pd
import numpy as np
import os
from llm_utils import get_embedder, get_reranker, get_llm, reload_embedder_reranker
from logger_config import logger, timed_log

class SearchEngine:
    def __init__(self, db_path="workspace/lancedb", table_name="knowledge_base", graph_engine=None):
        self.db_path = db_path
        if not os.path.exists(db_path):
            os.makedirs(db_path)
        self.db = lancedb.connect(db_path)
        self.table_name = table_name
        self.graph_engine = graph_engine

    def _ensure_embedder_reranker(self):
        reload_embedder_reranker()

    @timed_log
    def add_to_index(self, chunks):
        if not chunks: return

        self._ensure_embedder_reranker()
        embedder = get_embedder()

        texts = [c["text"] for c in chunks]
        vectors = embedder.encode(texts)
        logger.debug(f"Encoding {len(chunks)} chunks for index")
        data = []
        for i, chunk in enumerate(chunks):
            data.append({
                "vector": vectors[i],
                "text": chunk["text"],
                "filename": chunk["filename"],
                "pdf_path": chunk["pdf_path"],
                "page_num": chunk.get("page_num", 1)
            })

        if self.table_name in self.db.table_names():
            table = self.db.open_table(self.table_name)
            table.add(data)
        else:
            self.db.create_table(self.table_name, data=data)

    @timed_log
    def search(self, query, k=5):
        logger.info(f"Search query: \"{query}\"")
        if self.table_name not in self.db.table_names():
            return []

        self._ensure_embedder_reranker()
        embedder = get_embedder()
        reranker = get_reranker()

        table = self.db.open_table(self.table_name)
        query_vector = embedder.encode([query])[0]

        # 1. LanceDB Vector Search (Benzer metinleri bul)
        results = table.search(query_vector).limit(15).to_pandas()
        if results.empty: return []

        # 2. BGE Reranking (En alakalı olanları yukarı taşı)
        cross_inp = [[query, row["text"]] for _, row in results.iterrows()]
        rerank_scores = reranker.predict(cross_inp)
        results["rerank_score"] = rerank_scores
        results = results.sort_values(by="rerank_score", ascending=False).head(k)

        # 3. GraphRAG - Graf Bağlamını Çek
        graph_context = ""
        if self.graph_engine:
            all_entities = self.graph_engine.get_all_entities()
            found_entities = [e for e in all_entities if e.lower() in query.lower()]

            if not found_entities:
                top_text = results.iloc[0]['text']
                found_entities = [e for e in all_entities if e.lower() in top_text.lower()][:3]

            for ent in found_entities:
                paths = self.graph_engine.get_paths_from_entity(ent, depth=2)
                if paths:
                    graph_context += f"\n--- Graf Bilgisi ({ent}) ---\n"
                    for path in paths[:5]:
                        orbit = path.get("orbit", [])
                        if len(orbit) >= 2:
                            nodes = [n["node"] for n in orbit]
                            arrows = path.get("arrow_sequence", [])
                            graph_context += f"- {' -> '.join(nodes)} [{arrows[0] if arrows else 'related'}]\n"

        final_list = results.to_dict('records')
        if graph_context:
            final_list.append({
                "text": f"GRAF BAĞLAMI (İlişkisel Bilgi):\n{graph_context}",
                "filename": "Knowledge Graph",
                "pdf_path": None,
                "page_num": 0
            })

        return final_list