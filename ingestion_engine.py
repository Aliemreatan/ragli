# -*- coding: utf-8 -*-
import os
import hashlib
import json
import re
import fitz  # PyMuPDF
from datetime import datetime
from llm_utils import get_llm

class TwoStepIngestor:
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
        
        print(f"[{filename}] Okunuyor...")
        try:
            doc = fitz.open(filepath)
            full_text = ""
            for page in doc:
                full_text += page.get_text() + "\n"
            doc.close()
        except Exception as e:
            print(f"Hata: {e}")
            return None
        
        with open(os.path.join(self.raw_dir, f"{filename}.md"), "w", encoding="utf-8") as f:
            f.write(full_text)

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"hash": file_hash, "processed_at": str(datetime.now())}, f)

        return self._balanced_graph_ingest(full_text, filename, graph_engine)

    def _balanced_graph_ingest(self, text, filename, graph_engine=None):
        """Zengin veri çıkarımı ile hızı dengeleyen Ingest."""
        llm = get_llm()
        
        # Parça boyutunu 8.000 karakter yaparak LLM'e daha geniş bakış açısı veriyoruz.
        chunk_size = 8000 
        overlap = 600
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]
        
        print(f"[{filename}] {len(chunks)} büyük parça üzerinde Zengin Analiz başlatılıyor...")
        
        for i, chunk in enumerate(chunks):
            # Güvenlik sınırı: Çok dev dökümanlarda makul bir yerde dur (Örn: İlk 15 parça)
            if i > 15: break 
            
            print(f" > Zengin Analiz {i+1}/{min(len(chunks), 16)} işleniyor...")
            
            # ZENGİN PROMPT: Detayları koruyoruz.
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

METİN PARÇASI:
{chunk}
"""
            raw_res = llm.generate([{"role": "user", "content": prompt}], temperature=0.1)
            
            # JSON Çıkarımı ve Hata Kontrolü
            json_match = re.search(r'\{.*\}', raw_res.replace('\n', ' '), re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    if graph_engine:
                        for ent in data.get('entities', []):
                            graph_engine.add_entity(ent['name'], ent['type'], {'desc': ent.get('desc', '')})
                        for rel in data.get('relationships', []):
                            graph_engine.add_relationship(rel['source'], rel['target'], rel['type'], rel.get('weight', 1.0))
                except Exception as e:
                    print(f"JSON Ayrıştırma Sorunu (Parça {i+1}): {e}")

        if graph_engine: 
            graph_engine.save()
            print(f"[{filename}] Zengin Graf Başarıyla Güncellendi.")

        return {"raw_text": text, "wiki": "Zengin Ingest Tamamlandı."}
