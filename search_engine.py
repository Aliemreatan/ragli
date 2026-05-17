# -*- coding: utf-8 -*-
import lancedb
import pandas as pd
import numpy as np
import os
from llm_utils import get_embedder, get_reranker, get_llm

class SearchEngine:
    def __init__(self, db_path="workspace/lancedb", table_name="knowledge_base", graph_engine=None):
        self.db_path = db_path
        if not os.path.exists(db_path):
            os.makedirs(db_path)
        self.db = lancedb.connect(db_path)
        self.table_name = table_name
        self.graph_engine = graph_engine
        self.embedder = get_embedder()
        self.reranker = get_reranker()
        self.llm = get_llm()

    def add_to_index(self, chunks):
        if not chunks: return
        data = []
        for chunk in chunks:
            vector = self.embedder.encode([chunk["text"]])[0]
            data.append({
                "vector": vector,
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

    def search(self, query, k=5):
        if self.table_name not in self.db.table_names():
            return []
        
        table = self.db.open_table(self.table_name)
        query_vector = self.embedder.encode([query])[0]
        
        # 1. LanceDB Vector Search (Benzer metinleri bul)
        results = table.search(query_vector).limit(15).to_pandas()
        if results.empty: return []

        # 2. BGE Reranking (En alakalı olanları yukarı taşı)
        cross_inp = [[query, row["text"]] for _, row in results.iterrows()]
        rerank_scores = self.reranker.predict(cross_inp)
        results["rerank_score"] = rerank_scores
        results = results.sort_values(by="rerank_score", ascending=False).head(k)
        
        # 3. GraphRAG - Graf Bağlamını Çek
        graph_context = ""
        if self.graph_engine:
            # Sorgu içindeki kavramları basitçe eşleştir (Geliştirilebilir: LLM ile anahtar kelime çıkarma)
            all_entities = self.graph_engine.get_all_entities()
            found_entities = [e for e in all_entities if e.lower() in query.lower()]
            
            # Eğer doğrudan eşleşme yoksa, rerank edilen metinlerden varlık ara
            if not found_entities:
                top_text = results.iloc[0]['text']
                found_entities = [e for e in all_entities if e.lower() in top_text.lower()][:3]

            for ent in found_entities:
                ent_ctx = self.graph_engine.get_entity_context(ent)
                if ent_ctx:
                    graph_context += f"\n--- Graf Bilgisi ({ent}) ---\n{ent_ctx}\n"

        # Sonuçları listeye çevir ve Graf bağlamını ekle
        final_list = results.to_dict('records')
        if graph_context:
            # Graf bağlamını bir "özel hit" olarak ekleyelim ki LLM görsün
            final_list.append({
                "text": f"GRAF BAĞLAMI (İlişkisel Bilgi):\n{graph_context}",
                "filename": "Knowledge Graph",
                "pdf_path": None,
                "page_num": 0
            })
            
        return final_list
