# -*- coding: utf-8 -*-
import os
import io
import base64
import streamlit as st
import fitz
from PIL import Image
from ingestion_engine import TwoStepIngestor
from search_engine import SearchEngine
from graph_engine import GraphEngine
from llm_utils import get_embedder, get_reranker, get_llm


def render_pdf_base64(pdf_path, page_num=1, width=700):
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_url = f"data:application/pdf;base64,{b64}"
    st.components.v1.html(
        f"""
        <iframe src="{pdf_url}" width="{width}" height="900" style="border:none;"></iframe>
        """,
        height=950,
        scrolling=True
    )


def render_pdf_page_image(pdf_path, page_num=1, width=700):
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    st.image(buf.getvalue(), use_container_width=True)
    doc.close()

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
            total_files = len(uploaded_files)
            progress_bar = st.progress(0, text="Hazırlanıyor...")
            
            with st.spinner("İşleniyor (GraphRAG)..."):
                for i, file in enumerate(uploaded_files):
                    progress_bar.progress((i + 0.5) / total_files, text=f"İşleniyor: {file.name}")
                    path = os.path.join(st.session_state.ingestor.raw_dir, file.name)
                    with open(path, "wb") as f: f.write(file.getbuffer())
                    
                    res = st.session_state.ingestor.process_file(path, graph_engine=st.session_state.graph_engine)
                    
                    raw_md = os.path.join(st.session_state.ingestor.raw_dir, f"{file.name}.md")
                    with open(raw_md, "r", encoding="utf-8") as f:
                        text = f.read()
                    
                    chunks = []
                    page_num = 1
                    for page_text in text.split("\n\n\n"):
                        if len(page_text) < 20: continue
                        page_chunks = [{"text": p, "filename": file.name, "pdf_path": path, "page_num": page_num} 
                                      for p in page_text.split("\n\n") if len(p) > 40]
                        chunks.extend(page_chunks)
                        page_num += 1
                    
                    progress_bar.progress((i + 0.8) / total_files, text=f"Vektörle ekleniyor: {file.name}")
                    st.session_state.search_engine.add_to_index(chunks)
                    progress_bar.progress((i + 1) / total_files, text=f"Tamamlandı: {file.name}")
                
                progress_bar.empty()
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
        tab1, tab2 = st.tabs(["🌐 PDF Görüntüle", "🖼️ Sayfa Görüntüsü"])
        with tab1:
            render_pdf_base64(st.session_state.viewer_pdf_path,
                            page_num=st.session_state.viewer_page)
        with tab2:
            render_pdf_page_image(st.session_state.viewer_pdf_path,
                                 page_num=st.session_state.viewer_page,
                                 width=700)
    else:
        st.info("İlgili döküman burada görünecektir.")
