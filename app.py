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
from logger_config import logger

try:
    from streamlit_agraph import agraph, Node, Edge, Config
    AGRAPH_AVAILABLE = True
except ImportError:
    AGRAPH_AVAILABLE = False


def render_pdf_base64(pdf_path, page_num=1, width=700):
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_url = f"data:application/pdf;base64,{b64}"
    st.iframe(
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
    st.image(buf.getvalue(), width='stretch')
    doc.close()


st.set_page_config(page_title="QwenRaggity V2", page_icon="🧠", layout="wide")

if "graph_engine" not in st.session_state: st.session_state.graph_engine = GraphEngine()
if "ingestor" not in st.session_state: st.session_state.ingestor = TwoStepIngestor()
if "search_engine" not in st.session_state: st.session_state.search_engine = SearchEngine(graph_engine=st.session_state.graph_engine)
if "messages" not in st.session_state: st.session_state.messages = []
if "viewer_pdf_path" not in st.session_state: st.session_state.viewer_pdf_path = None
if "viewer_page" not in st.session_state: st.session_state.viewer_page = 1
if "selected_node" not in st.session_state: st.session_state.selected_node = None

embedder = get_embedder()
reranker = get_reranker()
llm = get_llm()

with st.sidebar:
    st.title("📂 Bilgi Yönetimi")
    uploaded_files = st.file_uploader("PDF/Text Yükle", type=["pdf", "txt", "md"], accept_multiple_files=True)
    if st.button("🚀 Verileri İşle", width='stretch'):
        if uploaded_files:
            total_files = len(uploaded_files)
            progress_bar = st.progress(0, text="Hazırlanıyor...")
            
            with st.spinner("İşleniyor (GraphRAG)..."):
                for i, file in enumerate(uploaded_files):
                    path = os.path.join(st.session_state.ingestor.raw_dir, file.name)
                    with open(path, "wb") as f: f.write(file.getbuffer())
                    
                    res = st.session_state.ingestor.process_file(
                        path, 
                        graph_engine=st.session_state.graph_engine,
                        progress_callback=None
                    )
                    
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
                    
                    progress_bar.progress((i + 0.9) / total_files, text=f"Vektörle ekleniyor: {file.name}")
                    st.session_state.search_engine.add_to_index(chunks)
                    progress_bar.progress(1.0, text=f"Tamamlandı: {file.name}")
                
                progress_bar.empty()
                st.success("İşlem Başarılı! (Graf ve Vektör Veritabanı Güncellendi)")

tab1, tab2 = st.tabs(["💬 Sohbet", "🔍 Bilgi Grafiği"])

with tab1:
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
            tab_p1, tab_p2 = st.tabs(["🌐 PDF Görüntüle", "🖼️ Sayfa Görüntüsü"])
            with tab_p1:
                render_pdf_base64(st.session_state.viewer_pdf_path,
                                page_num=st.session_state.viewer_page)
            with tab_p2:
                render_pdf_page_image(st.session_state.viewer_pdf_path,
                                     page_num=st.session_state.viewer_page,
                                     width=700)
        else:
            st.info("İlgili döküman burada görünecektir.")

with tab2:
    if not AGRAPH_AVAILABLE:
        st.warning("streamlit-agraph kütüphanesi yüklü değil. `pip install streamlit-agraph` ile yükleyin.")
    else:
        graph_engine = st.session_state.graph_engine
        stats = graph_engine.get_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Düğümler", stats["nodes"])
        col2.metric("İlişkiler", stats["edges"])
        col3.metric("Community'ler", stats["communities"])
        col4.metric("Yoğunluk", f"{stats['density']:.3f}")
        
        node_types = graph_engine.get_node_type_counts()
        if node_types:
            st.subheader("Varlık Tiplerine Göre Dağılım")
            for ntype, count in node_types.items():
                st.write(f"- {ntype}: {count}")
        
        col_search, col_type, col_comm = st.columns([2, 1, 1])
        with col_search:
            search_query = st.text_input("🔍 Düğüm ara...", key="node_search")
        with col_type:
            all_types = list(set(graph_engine.get_node_type_counts().keys()))
            type_filter = st.multiselect("Tip:", all_types if all_types else [], key="type_filter")
        
        TYPE_COLORS = {
            "Kişi": "#4285F4", "Kurum": "#34A853",
            "Teknik Kavram": "#9C27B0", "Olay": "#FF6D00",
            "Yer": "#00ACC1", "Ürün": "#FFD600", "Belge": "#78909C"
        }
        
        nodes = []
        edges = []
        filtered_nodes = set()
        
        all_entities = graph_engine.get_all_entities()
        for entity_id in all_entities:
            node_data = graph_engine.graph.nodes[entity_id]
            ntype = node_data.get('type', 'unknown')
            
            if search_query and search_query.lower() not in entity_id.lower():
                continue
            if type_filter and ntype not in type_filter:
                continue
            
            filtered_nodes.add(entity_id)
            nodes.append(Node(
                id=entity_id,
                label=entity_id,
                size=20,
                color=TYPE_COLORS.get(ntype, '#888')
            ))
        
        for src, tgt, data in graph_engine.graph.edges(data=True):
            if src in filtered_nodes and tgt in filtered_nodes:
                edges.append(Edge(
                    source=src,
                    target=tgt,
                    label=data.get('type', ''),
                    width=min(data.get('weight', 1.0), 3)
                ))
        
        if nodes:
            config = Config(width=700, height=500, directed=False, physics=True)
            selected = agraph(nodes=nodes, edges=edges, config=config)
            if selected:
                st.session_state.selected_node = selected
        else:
            st.info("Görüntülenecek düğüm bulunamadı. Önce PDF yükleyip işleyin.")
        
        if st.session_state.selected_node:
            node_id = st.session_state.selected_node
            st.subheader(f"Seçili Düğüm: {node_id}")
            node_data = graph_engine.graph.nodes[node_id]
            st.write(f"**Tip:** {node_data.get('type', 'unknown')}")
            st.write(f"**Açıklama:** {node_data.get('desc', 'Yok')}")
            
            neighbors = list(graph_engine.graph.neighbors(node_id))
            st.write(f"**Bağlantılar ({len(neighbors)}):**")
            for n in neighbors[:10]:
                rel_type = graph_engine.graph[node_id][n].get('type', 'ilişkili')
                st.write(f"  - {n} --[{rel_type}]-->")