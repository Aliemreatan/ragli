# -*- coding: utf-8 -*-
import os
import hashlib
import json
import re
import fitz  # PyMuPDF
from datetime import datetime
from llm_utils import get_llm

class TwoStepIngestor:
    """
    RAM dostu (PyMuPDF) ve Geniş Kapsamlı (Chunked) Ingest Motoru.
    Docling yerine PyMuPDF kullanarak 10GB+ RAM tasarrufu sağlar.
    """
    def __init__(self, workspace_dir="workspace"):
        self.workspace_dir = workspace_dir
        self.raw_dir = os.path.join(workspace_dir, "raw")
        self.wiki_dir = os.path.join(workspace_dir, "wiki")
        
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
        file_hash = self._get_file_hash(filepath)
        filename = os.path.basename(filepath)
        
        cache_path = os.path.join(self.raw_dir, f"{filename}.meta.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r") as f:
                meta = json.load(f)
                if meta.get("hash") == file_hash:
                    print(f"[{filename}] Cache Hit - Atlanıyor.")
                    return None
        
        print(f"[{filename}] PyMuPDF ile okunuyor...")
        try:
            doc = fitz.open(filepath)
            full_text = ""
            for page in doc:
                full_text += page.get_text() + "\n"
            doc.close()
        except Exception as e:
            print(f"Okuma Hatası: {e}")
            return None
        
        # Ham metni kaydet
        with open(os.path.join(self.raw_dir, f"{filename}.md"), "w", encoding="utf-8") as f:
            f.write(full_text)

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"hash": file_hash, "processed_at": str(datetime.now())}, f)

        return self._wide_graph_llm_ingest(full_text, filename, graph_engine)

    def _wide_graph_llm_ingest(self, text, filename, graph_engine=None):
        """Metni parçalara böler ve her parçadan derinlemesine graf çıkarır."""
        llm = get_llm()
        
        # Metni ~3000 karakterlik parçalara böl (üst üste binmeli/overlap)
        chunk_size = 3000
        overlap = 300
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]
        
        print(f"[{filename}] {len(chunks)} parça üzerinde Geniş Graf Analizi başlatılıyor...")
        
        for i, chunk in enumerate(chunks):
            if i > 15: break # Çok uzun dökümanlarda sınırı koru (Ayarlanabilir)
            print(f" > Parça {i+1}/{min(len(chunks), 16)} işleniyor...")
            
            analysis_prompt = f"""
Metni analiz et ve Varlıklar (Entity) ile İlişkileri (Relationship) çıkar.
Özellikle gizli kalmış, dolaylı bağlantıları ve teknik detayları yakala.
Çıktıyı MUTLAKA sadece şu JSON formatında ver:
{{
  "entities": [{{ "name": "...", "type": "...", "desc": "..." }}],
  "relationships": [{{ "source": "...", "target": "...", "type": "...", "weight": 1.5 }}]
}}

METİN PARÇASI:
{chunk}
"""
            raw_res = llm.generate([{"role": "user", "content": analysis_prompt}], temperature=0.1)
            
            # JSON Çıkarımı
            json_match = re.search(r'\{.*\}', raw_res.replace('\n', ' '), re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    if graph_engine:
                        for ent in data.get('entities', []):
                            graph_engine.add_entity(ent['name'], ent['type'], {'desc': ent.get('desc', '')})
                        for rel in data.get('relationships', []):
                            graph_engine.add_relationship(rel['source'], rel['target'], rel['type'], rel.get('weight', 1.0))
                except: pass

        if graph_engine: 
            graph_engine.save()
            print(f"[{filename}] Graf başarıyla güncellendi.")

        return {"raw_text": text, "wiki": "Analiz tamamlandı. Graf güncellendi."}
