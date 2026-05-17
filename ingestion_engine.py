# -*- coding: utf-8 -*-
import os
import hashlib
import json
import re
from datetime import datetime
from docling.document_converter import DocumentConverter
from llm_utils import get_llm

class TwoStepIngestor:
    """
    LLM Wiki'den ilham alan İki Aşamalı İçerik İşleme Motoru (Two-Step Chain-of-Thought Ingest)
    ve GraphRAG'in Varlık/İlişki çıkarma mekanizmasını entegre eder.
    """
    def __init__(self, workspace_dir="workspace"):
        self.workspace_dir = workspace_dir
        self.raw_dir = os.path.join(workspace_dir, "raw")
        self.wiki_dir = os.path.join(workspace_dir, "wiki")
        self.converter = DocumentConverter()
        
        for d in [self.raw_dir, self.wiki_dir]:
            if not os.path.exists(d):
                os.makedirs(d)

    def _get_file_hash(self, filepath):
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    def process_file(self, filepath, graph_engine=None):
        """1. Adım: Orijinal dosyadan metin ve hash çıkar."""
        file_hash = self._get_file_hash(filepath)
        filename = os.path.basename(filepath)
        
        # Incremental Cache
        cache_path = os.path.join(self.raw_dir, f"{filename}.meta.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r") as f:
                meta = json.load(f)
                if meta.get("hash") == file_hash:
                    print(f"[{filename}] Değişiklik yok, ingest atlanıyor (Cache Hit).")
                    return None
        
        print(f"[{filename}] Docling ile dönüştürülüyor...")
        doc = self.converter.convert(filepath)
        text = doc.document.export_to_markdown()
        
        # Orijinal metni raw dizinine kaydet
        raw_md_path = os.path.join(self.raw_dir, f"{filename}.md")
        with open(raw_md_path, "w", encoding="utf-8") as f:
            f.write(text)

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"hash": file_hash, "processed_at": str(datetime.now())}, f)

        return self._two_step_llm_ingest(text, filename, graph_engine)

    def _two_step_llm_ingest(self, text, filename, graph_engine=None):
        """2. Adım: LLM Wiki & GraphRAG birleşimi Chain-of-Thought"""
        llm = get_llm()
        
        # ADIM 1: YAPI KAPSAMINDA ANALİZ (JSON formatında)
        analysis_prompt = f"""
Metni analiz et ve varlıkları (entities) ve ilişkileri (relationships) bul.
Çıktıyı MUTLAKA şu JSON formatında ver:
{{
  "entities": [{{ "name": "...", "type": "Kişi/Kurum/Kavram", "desc": "..." }}],
  "relationships": [{{ "source": "...", "target": "...", "type": "...", "weight": 1.0 }}]
}}

METİN:
{text[:3500]}
"""
        messages = [{"role": "user", "content": analysis_prompt}]
        print(f"[{filename}] Varlık/İlişki çıkarımı başlatılıyor...")
        raw_json_res = llm.generate(messages, temperature=0.1)
        
        # JSON temizleme (Markdown kod blokları varsa temizle)
        json_str = re.search(r'\{.*\}', raw_json_res.replace('\n', ' '), re.DOTALL)
        if json_str:
            try:
                graph_data = json.loads(json_str.group())
                if graph_engine:
                    for ent in graph_data.get('entities', []):
                        graph_engine.add_entity(ent['name'], ent['type'], {'desc': ent.get('desc', '')})
                    for rel in graph_data.get('relationships', []):
                        graph_engine.add_relationship(rel['source'], rel['target'], rel['type'], rel.get('weight', 1.0))
                    graph_engine.save()
                    print(f"[{filename}] {len(graph_data.get('entities', []))} varlık grafa eklendi.")
            except Exception as e:
                print(f"JSON Ayrıştırma Hatası: {e}")

        # ADIM 2: ÜRETİM (Wiki sayfası)
        generation_prompt = "Önceki analizine dayanarak Obsidian uyumlu bir Wiki sayfası oluştur. [[wikilinks]] kullan."
        messages.append({"role": "assistant", "content": raw_json_res})
        messages.append({"role": "user", "content": generation_prompt})
        
        wiki_content = llm.generate(messages, temperature=0.3)
        wiki_page_path = os.path.join(self.wiki_dir, f"{filename}.wiki.md")
        with open(wiki_page_path, "w", encoding="utf-8") as f:
            f.write(wiki_content)
            
        return {"raw_text": text, "wiki": wiki_content}

# Multi-modal görüntü analizi de burada eklenebilir. (Gelecek Vizyonu)
class MultimodalExtractor:
    def extract_images_and_caption(self, pdf_path):
        # PyMuPDF ile resim çıkarma ve Qwen-VL (Vision) modeline gönderme işlemleri (Placeholder)
        pass
