# -*- coding: utf-8 -*-
"""
Mock SSTorytime Semantic Spacetime Graph Interface
For development/testing before real PostgreSQL integration.
"""
import uuid
import time
from collections import defaultdict
from typing import Optional, List, Dict, Any


class MockVertex:
    def __init__(self, name: str, vtype: str = "unknown", properties: Dict = None):
        self.name = name
        self.type = vtype
        self.properties = properties or {}
        self.id = str(uuid.uuid4())[:8]

    def __repr__(self):
        return f"Vertex({self.name}, type={self.type})"


class MockEdge:
    def __init__(self, source: str, target: str, arrow: str, weight: float = 1.0):
        self.source = source
        self.target = target
        self.arrow = arrow
        self.weight = weight
        self.id = str(uuid.uuid4())[:8]

    def __repr__(self):
        return f"Edge({self.source} -[{self.arrow}]-> {self.target})"


class MockSSTorytimeDB:
    def __init__(self):
        self.vertices = {}  # name -> MockVertex
        self.edges = []     # List[MockEdge]
        self.arrows = set()  # registered arrow types

    def register_arrow(self, arrow_name: str):
        self.arrows.add(arrow_name)


class SSTorytime:
    """
    Mock SSTorytime interface mimicking the real API.
    The real implementation uses psycopg2 to connect to PostgreSQL.
    """

    ARROWS = {
        "causality": "->",
        "containment": ">>",
        "similarity": "<->",
        "expression": "~>"
    }

    def __init__(self, db_path: str = None, config_path: str = None):
        self.db = MockSSTorytimeDB()
        self._connected = True

    def Open(self, db_name: str) -> bool:
        """Open database connection - mock always succeeds"""
        self._connected = True
        return True

    def Vertex(self, name: str, vtype: str = "unknown", **properties) -> bool:
        """Create or update a vertex"""
        self.db.vertices[name] = MockVertex(name, vtype, properties)
        return True

    def Edge(self, source: str, target: str, arrow: str = "related_to", weight: float = 1.0) -> bool:
        """Create an edge between two vertices"""
        if source not in self.db.vertices:
            self.db.vertices[source] = MockVertex(source)
        if target not in self.db.vertices:
            self.db.vertices[target] = MockVertex(target)

        edge = MockEdge(source, target, arrow, weight)
        self.db.edges.append(edge)

        if arrow not in self.db.arrows:
            self.db.register_arrow(arrow)

        return True

    def GetFwdPathsAsLinks(self, entity_name: str, depth: int = 1, arrow_types: List[str] = None) -> List[Dict]:
        """
        Get forward paths (causal cone) from an entity.
        Returns list of path dictionaries.

        Real SSTorytime: SELECT * FROM paths WHERE source = entity
        Mock: simple BFS traversal
        """
        if entity_name not in self.db.vertices:
            return []

        paths = []
        arrow_filter = set(arrow_types) if arrow_types else None

        def bfs(current, visited: set, depth_left: int):
            if depth_left <= 0:
                return

            for edge in self.db.edges:
                if edge.source == current:
                    if arrow_filter and edge.arrow not in arrow_filter:
                        continue
                    if edge.target in visited:
                        continue

                    path = {
                        "path_id": str(uuid.uuid4())[:8],
                        "orbit": [
                            {"node": edge.source, "type": self.db.vertices[edge.source].type},
                            {"node": edge.target, "type": self.db.vertices[edge.target].type}
                        ],
                        "arrow": edge.arrow,
                        "distance": 1,
                        "arrow_sequence": [edge.arrow]
                    }
                    paths.append(path)

                    visited.add(edge.target)
                    bfs(edge.target, visited.copy(), depth_left - 1)

        bfs(entity_name, {entity_name}, depth)
        return paths

    def GetEntireNCConePathsAsLinks(self, entity_name: str, depth: int = 2) -> List[Dict]:
        """
        Get entire neighborhood causal cone paths (broader semantic search).
        Combines forward and backward traversals.

        Real SSTorytime: SELECT * FROM paths WHERE entity IN (neighborhood)
        """
        if entity_name not in self.db.vertices:
            return []

        all_nodes = {entity_name}

        def collect_neighbors(start, d):
            if d <= 0:
                return
            for edge in self.db.edges:
                if edge.source == start:
                    all_nodes.add(edge.target)
                    collect_neighbors(edge.target, d - 1)
                if edge.target == start:
                    all_nodes.add(edge.source)
                    collect_neighbors(edge.source, d - 1)

        collect_neighbors(entity_name, depth)

        paths = []
        for node in all_nodes:
            node_paths = self.GetFwdPathsAsLinks(node, depth=1)
            paths.extend(node_paths)

        return paths

    def GetPathsBetween(self, source: str, target: str, max_depth: int = 3) -> List[Dict]:
        """Find all paths between two entities"""
        if source not in self.db.vertices or target not in self.db.vertices:
            return []

        paths = []

        def dfs(current, target, visited: set, path: list):
            if current == target:
                paths.append({
                    "path_id": str(uuid.uuid4())[:8],
                    "orbit": path.copy(),
                    "distance": len(path) - 1
                })
                return

            for edge in self.db.edges:
                if edge.source == current and edge.target not in visited:
                    visited.add(edge.target)
                    path.append({"node": edge.target, "type": self.db.vertices[edge.target].type, "arrow": edge.arrow})
                    dfs(edge.target, target, visited, path)
                    path.pop()
                    visited.remove(edge.target)

        initial_path = [{"node": source, "type": self.db.vertices[source].type}]
        dfs(source, target, {source}, initial_path)

        return paths

    def GetNodeOrbit(self, entity_name: str) -> Dict:
        """Get direct orbit (1-hop neighbors) of a node"""
        orbit = {
            "entity": entity_name,
            "type": self.db.vertices.get(entity_name, MockVertex(entity_name)).type,
            "incoming": [],
            "outgoing": []
        }

        for edge in self.db.edges:
            if edge.target == entity_name:
                orbit["incoming"].append({
                    "source": edge.source,
                    "arrow": edge.arrow,
                    "weight": edge.weight
                })
            if edge.source == entity_name:
                orbit["outgoing"].append({
                    "target": edge.target,
                    "arrow": edge.arrow,
                    "weight": edge.weight
                })

        return orbit

    def GetStats(self) -> Dict:
        """Get graph statistics"""
        return {
            "vertices": len(self.db.vertices),
            "edges": len(self.db.edges),
            "arrows": len(self.db.arrows),
            "arrow_types": list(self.db.arrows)
        }

    def QueryByArrow(self, arrow_type: str) -> List[Dict]:
        """Query all edges of a specific arrow type"""
        results = []
        for edge in self.db.edges:
            if edge.arrow == arrow_type:
                results.append({
                    "source": edge.source,
                    "target": edge.target,
                    "arrow": edge.arrow,
                    "weight": edge.weight
                })
        return results


def example_output():
    """
    Generate example output showing what SSTorytime path queries return.
    This helps visualize the data format for the visualization decision.
    """
    sst = SSTorytime()

    sst.Vertex("Kara Şimşek", "Kişi")
    sst.Vertex("Elektrik", "Teknik Kavram")
    sst.Vertex("Yüksek Gerilim Hattı", "Yer")
    sst.Vertex("Enerji İletimi", "Olay")
    sst.Vertex("Türkiye", "Yer")

    sst.Edge("Kara Şimşek", "Elektrik", "kullanır", 1.0)
    sst.Edge("Elektrik", "Yüksek Gerilim Hattı", "iletilir", 0.8)
    sst.Edge("Yüksek Gerilim Hattı", "Enerji İletimi", "parçasıdır", 0.9)
    sst.Edge("Enerji İletimi", "Türkiye", "gerçekleşir", 0.7)
    sst.Edge("Kara Şimşek", "Türkiye", "bulunur", 0.6)

    print("=" * 70)
    print("SSTORYTIME API ÇIKTı ÖRNEKLERİ")
    print("=" * 70)

    print("\n1. GetNodeOrbit('Kara Şimşek'):")
    orbit = sst.GetNodeOrbit("Kara Şimşek")
    import json
    print(json.dumps(orbit, indent=2, ensure_ascii=False))

    print("\n2. GetFwdPathsAsLinks('Kara Şimşek', depth=2):")
    paths = sst.GetFwdPathsAsLinks("Kara Şimşek", depth=2)
    print(json.dumps(paths, indent=2, ensure_ascii=False))

    print("\n3. GetEntireNCConePathsAsLinks('Elektrik', depth=2):")
    nc_paths = sst.GetEntireNCConePathsAsLinks("Elektrik", depth=2)
    print(json.dumps(nc_paths, indent=2, ensure_ascii=False))

    print("\n4. GetStats():")
    stats = sst.GetStats()
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    print("\n" + "=" * 70)
    print("GRAF GÖRSELLEŞTİRME ÖNERİSİ:")
    print("=" * 70)
    print("""
SSTorytime path yapısı (orbit/sequence) networkx graph'tan farklıdır.
Her path bir yönlü dizi (sequence) içerir:

  [A] --[causality]--> [B] --[containment]--> [C]

Visualization seçenekleri:
  A) Path List View: Her yolu bir satır olarak göster
     ├── Kara Şimşek --[kullanır]--> Elektrik
     └── Elektrik --[iletilir]--> Yüksek Gerilim Hattı

  B) Node-Centered Orbit View: Seçili node'un tüm bağlantılarını
     bir merkez etrafında göster (star pattern)

  C) GraphQL-style Schema: Bağlantı tiplerine göre grupla
    """)


if __name__ == "__main__":
    example_output()