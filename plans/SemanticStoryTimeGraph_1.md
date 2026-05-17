Semantic Spacetime Story Integration Plan
Goal: Replace the NetworkX graph engine in KNRAG with the SSTorytime Semantic Spacetime graph database, bypassing the MCP layer and using native Python/PostgreSQL integration.
1. Architecture Overview
Why This Approach?
- 
No MCP Client Needed: We bypass MCP-SST entirely. SSTorytime exposes a native Python module (SSTorytime.py) that uses psycopg2 to talk directly to PostgreSQL.
- 
No Prebuilt Binaries: We install Go and PostgreSQL on the Vast AI Linux instance and build SSTorytime from source via make. This is standard and maintainable.
- 
N4L as Data Bridge: LLM-extracted entities/relationships are translated into N4L text files (SSTorytime's native note format), then compiled and uploaded to PostgreSQL using the N4L CLI tool. This is the idiomatic way to populate SSTorytime and handles arrow (relation type) registration automatically.
- 
Semantic Spacetime Queries: We replace networkx traversals with SSTorytime's path algorithms (GetFwdPathsAsLinks, GetEntireNCConePathsAsLinks) which resolve relations based on causality, containment, similarity, and expression (the 4 ST types).
Architecture Changes
- 
Graph Storage: Move from networkx + graph.json to PostgreSQL (SSTorytime schema).
- 
Graph Queries: Use SSTorytime.py Python API (Open, Vertex, Edge, path queries) instead of networkx traversals.
- 
Search Integration: The search engine will pull graph context using SSTorytime's causal cone search (GetFwdPathsAsLinks) and combined semantic search (GetEntireNCConePathsAsLinks).
- 
Ingestion: LLM outputs JSON entities/relationships → translated to .in (N4L) files → uploaded to DB via N4L -u.
2. Pre-Run Installation Script (setup_sstorytime.sh)
Purpose
This is a standalone script designed for a fresh Vast AI instance. It handles uv init && sync, installs PostgreSQL and Go, builds SSTorytime, and initializes the database.
#!/bin/bash
set -e
echo "========================================================"
echo "🚀 KNRAG + SSTorytime Integration Kurulumu"
echo "========================================================"
# --- 1. UV Environment Setup ---
echo "📦 1. Python ortami (uv) hazirlaniyor..."
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi
uv init --python 3.11
uv sync
uv pip install psycopg2-binary  # Ensure SSTorytime.py dependency is available
# --- 2. System Dependencies (PostgreSQL + Go) ---
echo "📦 2. PostgreSQL ve Go kuruluyor..."
apt-get update && apt-get install -y postgresql postgresql-contrib golang-go git build-essential
# --- 3. PostgreSQL Configuration ---
echo "🐘 3. PostgreSQL baslatiliyor ve yapilandiriliyor..."
service postgresql start || true
# Create SSTorytime user and database
sudo -u postgres psql -c "CREATE USER sstoryline WITH PASSWORD 'sst_1234';" || true
sudo -u postgres psql -c "CREATE DATABASE sstoryline OWNER sstoryline;" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE sstoryline TO sstoryline;" || true
# --- 4. Build SSTorytime Binaries ---
echo "🔨 4. SSTorytime kaynaklari indiriliyor ve derleniyor..."
SST_DIR="$HOME/SSTorytime"
if [ ! -d "$SST_DIR" ]; then
    git clone https://github.com/markburgess/SSTorytime.git "$SST_DIR"
fi
cd "$SST_DIR"
make  # Builds N4L compiler and http_server
# Ensure binaries are in PATH
mkdir -p $HOME/.local/bin
cp src/N4L src/http_server $HOME/.local/bin/ || true
export PATH="$HOME/.local/bin:$PATH"
# --- 5. Initialize SSTorytime Database Schema ---
echo "🗄️ 5. SSTorytime veritabani semasi yukleniyor..."
cd "$SST_DIR/src"
sudo -u postgres psql -d sstoryline -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" || true
# --- 6. Download Python Integration Module ---
echo "🐍 6. SSTorytime Python modulu hazirlaniyor..."
cp "$SST_DIR/src/SSTorytime.py" "$OLDPWD/workspace/SSTorytime.py" || true
echo "========================================================"
echo "✅ KURULUM TAMAMLANDI!"
echo "========================================================"
echo "Ortam degiskenleri:"
echo "export PATH=\"$HOME/.local/bin:\$PATH\""
echo "export SST_CONFIG_PATH=\"$SST_DIR/SSTconfig\""
echo ""
echo "Uygulamayi baslatmadan once PostgreSQL'in calistigundan emin olun:"
echo "  service postgresql start"
echo ""
echo "Ardindan 'python runner.py' ile KNRAG'i baslatabilirsiniz."
Integration Notes
- 
uv init && uv sync: Ensures pyproject.toml dependencies are installed in the isolated .venv.
- 
psycopg2-binary: Added explicitly because SSTorytime.py requires it.
- 
PostgreSQL User: SSTorytime expects a user named sstoryline with password sst_1234 by default.
- 
SSTconfig Path: SSTorytime needs the SSTconfig/ directory (arrow definitions). The script sets SST_CONFIG_PATH accordingly.
3. Files to Modify
3.1 graph_engine.py (Rewrite)
- 
Replace networkx.Graph with SSTorytime.Open() connection.
- 
Replace add_entity / add_relationship with SSTorytime.Vertex() and SSTorytime.Edge().
- 
Replace get_entity_context with SSTorytime.GetFwdPathsAsLinks() to perform causal cone lookups.
- 
Replace detect_communities with SSTorytime path-solving or Eigenvector centrality logic.
- 
Remove save()/load() JSON logic (data is persisted in PostgreSQL).
- 
Update get_stats() to query PostgreSQL counts.
3.2 ingestion_engine.py (Modify)
- 
After LLM extracts JSON entities/relationships, translate them into N4L .in text files.
- 
Register relations as SST arrows (use standard SSTconfig arrows where possible, or define new ones in SSTconfig/arrows-LT-1.sst if needed).
- 
Shell out to N4L -u <filename>.in to upload to the database.
- 
Add metadata tracking to prevent duplicate uploads (use file hash, similar to current logic).
3.3 search_engine.py (Modify)
- 
Keep LanceDB vector search as-is.
- 
In the GraphRAG enrichment step, instead of using graph_engine.get_all_entities() and networkx.neighbors(), query the SST database for:
- 
Node orbits around found entities (GetFwdPathsAsLinks).
- 
Broader semantic cones (GetEntireNCConePathsAsLinks) to fetch related concepts.
- 
Convert SST path results into the same text context format the LLM prompt currently expects.
3.4 app.py (Modify)
- 
Update Streamlit graph visualization to render based on SST query results (paths/orbits) instead of networkx + agraph.
- 
The right panel (Kaynak İzleyici) remains unchanged.
- 
The middle panel (Bilgi Grafiği) will fetch data from graph_engine.py (now SST-backed) and visualize path structures.
3.5 pyproject.toml (Modify)
- 
Add psycopg2-binary to dependencies.
3.6 runner.py (Modify)
- 
Ensure service postgresql start is executed before launching Streamlit.
4. Data Flow
User uploads PDF
    │
    ▼
ingestion_engine.py (LLM extracts entities/relationships)
    │
    ▼
JSON → N4L Translator (.in files)
    │
    ▼
N4L -u → PostgreSQL (SSTorytime Schema)
    │
    ▼
search_engine.py
    ├── LanceDB (Vector Search - unchanged)
    │
    └── SSTorytime DB (Graph Context Retrieval)
            │
            ├── Node/Entity Lookup
            ├── Forward Path (Cone) Search
            └── Community/Centrality Insights
    │
    ▼
LLM Prompt (Vector Results + SST Graph Context)
    │
    ▼
Streamlit Response
5. Open Questions / Risks
- 
N4L Arrow Compatibility: If LLM outputs arbitrary relationship types not in SSTconfig, we need a fallback to register custom arrows or map them to existing SST concepts.
- 
Visualization: streamlit-agraph may not easily render SST path structures (which are directed sequences/orbits). We might need to render raw path lists or switch to a different vis library.
- 
Performance: N4L -u is a shell command per ingestion batch. For large PDFs, batching into a single .in file is preferred.
