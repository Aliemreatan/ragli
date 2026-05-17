# SSTorytime Semantic Spacetime Graph Entegration

## Overview

KNRAG's graph engine has been migrated from NetworkX to SSTorytime, a semantic spacetime graph database built on PostgreSQL. This integration provides causal path queries and semantic cone search capabilities.

## Architecture Changes

### 1. New File: `sstorytime_mock.py`
Mock SSTorytime interface for development/testing. Provides the same API as the real PostgreSQL-backed implementation.

**Key Classes:**
- `SSTorytime` - Main database interface
- `MockVertex` / `MockEdge` - Data structures

**Main Methods:**
- `Open(db_name)` - Open database connection
- `Vertex(name, vtype, **properties)` - Create/update vertex
- `Edge(source, target, arrow, weight)` - Create edge
- `GetFwdPathsAsLinks(entity, depth)` - Forward causal cone search
- `GetEntireNCConePathsAsLinks(entity, depth)` - Neighborhood causal cone search
- `GetNodeOrbit(entity)` - Get incoming/outgoing links for a node

### 2. Modified: `graph_engine.py`
Replaced NetworkX dependency with SSTorytime API.

**Changes:**
- `__init__` - Initializes SSTorytime connection instead of loading JSON
- `add_entity()` / `add_relationship()` - Use SSTorytime.Vertex/Edge
- `get_entity_context()` - Uses GetFwdPathsAsLinks for multi-hop context
- `detect_communities()` - Still uses igraph/leidenalg via graph bridge
- `get_stats()` - Queries SSTorytime stats instead of networkx
- New methods: `get_paths_from_entity()`, `get_nc_cone_paths()`, `get_node_orbit()`

### 3. Modified: `ingestion_engine.py`
Added N4L translation layer for idiomatic SSTorytime data ingestion.

**Changes:**
- Added `N4LTranslator` class
- `json_to_n4l()` - Converts LLM JSON output to N4L `.in` format
- After graph insertion, writes N4L file for potential CLI upload

### 4. Modified: `search_engine.py`
Graph context retrieval now uses SSTorytime path queries.

**Changes:**
- `search()` - Uses `get_paths_from_entity()` instead of `get_entity_context()`
- Returns path sequences instead of simple neighbor lists

### 5. Modified: `app.py`
Two new visualization tabs replace the old agraph view:

**📋 Path List View (Tab A):**
- Shows directed path sequences
- Format: `Node1 → Node2 → Node3 [arrow_type]`
- Depth configurable via entity selection

**🔵 Orbit View (Tab B):**
- Star-pattern visualization centered on selected node
- Shows outgoing links (→) and incoming links (←) separately
- Uses streamlit-agraph for graph rendering

## Data Flow

```
PDF Upload
    ↓
ingestion_engine.py (LLM extracts entities/relationships)
    ↓
JSON → N4L Translator (.in files generated)
    ↓
graph_engine.py (SSTorytime.Vertex/Edge calls)
    ↓
SSTorytime DB (PostgreSQL)
    ↓
search_engine.py
    ├── LanceDB (Vector Search - unchanged)
    └── SSTorytime paths (Graph Context)
    ↓
LLM Prompt
    ↓
Streamlit Response
```

## Arrow Types

SSTorytime uses arrows for relation types. The mock implementation registers any arrow type encountered. Common arrows:
- `causality` (→)
- `containment` (>>)
- `similarity` (<->)
- `expression` (~>)
- Any custom string (e.g., "kullanır", "iletilir")

## Production Deployment

When deploying with real SSTorytime:
1. Run `setup_sstorytime.sh` on Vast AI instance
2. Replace `sstorytime_mock.py` with real `SSTorytime.py`
3. N4L files can be uploaded via `N4L -u <filename>.in`

## Testing

The mock allows full testing without PostgreSQL:
```python
from sstorytime_mock import SSTorytime
sst = SSTorytime()
sst.Vertex("Test Entity", "test_type")
sst.Edge("A", "B", "related_to")
paths = sst.GetFwdPathsAsLinks("A", depth=2)
```