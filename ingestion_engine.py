# -*- coding: utf-8 -*-
import os
import hashlib
import json
import re
import fitz  # PyMuPDF
from datetime import datetime
from llm_utils import get_llm
from logger_config import logger, timed_log

class TwoStepIngestor:
    def __init__(self, workspace_dir="workspace"):
        self.workspace_dir = workspace_dir
        self.raw_dir = os.path.join(workspace_dir, "raw")
        self.wiki_dir = os.path.join(workspace_dir, "wiki")

        for d in [self.raw_dir, self.wiki_dir]:
            if not os.path.exists(d):
                os.makedirs(d)

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

        chunk_size = 16000
        overlap = 200
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]

        logger.info(f"[{filename}] {len(chunks)} büyük parça üzerinde Zengin Analiz başlatılıyor...")

        for i, chunk in enumerate(chunks):
            if i > 7: break
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

METİN PARÇASI:
{chunk}
"""
            raw_res = llm.generate([{"role": "user", "content": prompt}], temperature=0.1, max_new_tokens=2048)

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
                    logger.error(f"[{filename}] JSON Ayrıştırma Sorunu (Parça {i+1}): {e}")

        if graph_engine:
            graph_engine.save()
            logger.info(f"[{filename}] Zengin Graf Başarıyla Güncellendi.")

        return {"raw_text": text, "wiki": "Zengin Ingest Tamamlandı."}
