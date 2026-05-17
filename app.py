# -*- coding: utf-8 -*-
import os
import streamlit as st
from streamlit_pdf_viewer import pdf_viewer
from ingestion_engine import TwoStepIngestor
from search_engine import SearchEngine
from graph_engine import GraphEngine
from llm_utils import get_embedder, get_reranker, get_llm

st.set_page_config(page_title="QwenRaggity V2", page_icon="🧠", layout="wide")

# State Initialization
if "graph_engine" not in st.session_state: st.session_state.graph_engine = GraphEngine()
if "ingestor" not in st.session_state: st.session_state.ingestor = TwoStepIngestor()
if "search_engine" not in st.session_state: st.session_state.search_engine = SearchEngine(graph_engine=st.session_state.graph_engine)
if "messages" not in st.session_state: st.session_state.messages = []
if "viewer_pdf_path" not in st.session_state: st.session_state.viewer_pdf_path = None
if "viewer_page" not in st.session_state: st.session_state.viewer_page = 1

# Modelleri yükle (Singleton)
embedder = get_embedder()
reranker = get_reranker()
llm = get_llm()

# Sidebar
with st.sidebar:
    st.title("📂 Bilgi Yönetimi")
    uploaded_files = st.file_uploader("PDF/Text Yükle", type=["pdf", "txt", "md"], accept_multiple_files=True)
    if st.button("🚀 Verileri İşle", use_container_width=True):
        if uploaded_files:
            with st.spinner("İşleniyor (2-Step Ingest & GraphRAG)..."):
                for file in uploaded_files:
                    path = os.path.join(st.session_state.ingestor.raw_dir, file.name)
                    with open(path, "wb") as f: f.write(file.getbuffer())
                    
                    # Graf motorunu da gönderiyoruz
                    res = st.session_state.ingestor.process_file(path, graph_engine=st.session_state.graph_engine)
                    
                    # Parçalara ayır ve vektör indeksine ekle
                    import fitz
                    doc = fitz.open(path)
                    chunks = []
                    for i, page in enumerate(doc):
                        text = page.get_text()
                        # Sayfa bazlı chunking
                        page_chunks = [{"text": p, "filename": file.name, "pdf_path": path, "page_num": i+1} for p in text.split("\n\n") if len(p) > 40]
                        chunks.extend(page_chunks)
                    st.session_state.search_engine.add_to_index(chunks)
                    doc.close()
                st.success("İşlem Başarılı! (Graf ve Vektör Veritabanı Güncellendi)")

# Chat & Viewer Layout
c1, c2 = st.columns([6, 4])
with c1:
    st.title("🧠 QwenRaggity V2")
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("Sorunuz..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.spinner("Düşünüyor..."):
            hits = st.session_state.search_engine.search(prompt)
            context = "\n".join([f"[KAYNAK {i+1}]: {h['text']}" for i, h in enumerate(hits)])
            system = f"Sen profesyonel bir asistan olan QwenRaggity V2'sin. Sadece bağlama göre cevap ver.\n\nBAĞLAM:\n{context}"
            
            with st.chat_message("assistant"):
                resp = st.write_stream(llm.generate([{"role": "system", "content": system}, {"role": "user", "content": prompt}], stream=True))
                st.session_state.messages.append({"role": "assistant", "content": resp})
            
            if hits:
                st.session_state.viewer_pdf_path = hits[0]['pdf_path']
                st.session_state.viewer_page = hits[0].get('page_num', 1)
                st.rerun()

with c2:
    st.title("📄 Kaynak İzleyici")
    if st.session_state.viewer_pdf_path and os.path.exists(st.session_state.viewer_pdf_path):
        with open(st.session_state.viewer_pdf_path, "rb") as f:
            pdf_viewer(f.read(), width=700, pages_to_render=[st.session_state.viewer_page])
    else:
        st.info("İlgili döküman burada görünecektir.")
