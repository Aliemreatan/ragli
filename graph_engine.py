# -*- coding: utf-8 -*-
import os
import json
from collections import Counter
from sstorytime_mock import SSTorytime

try:
    import igraph as ig
    import leidenalg
    LEIDEN_AVAILABLE = True
except ImportError:
    LEIDEN_AVAILABLE = False

from logger_config import logger, timed_log



class GraphEngine:
    def __init__(self, storage_path="workspace/graph.json", db_path="workspace/sstorytime_db"):
        self.storage_path = storage_path
        self.db_path = db_path
        logger.info(f"GraphEngine init: loading SSTorytime mock...")
        self.sst = SSTorytime(db_path)
        result = self.sst.Open("knrag")
        logger.info(f"GraphEngine SSTorytime Open result: {result}")
        self._communities_cache = None
        logger.info(f"GraphEngine initialized with {len(self.sst.db.vertices)} existing vertices, {len(self.sst.db.edges)} edges")

    def add_entity(self, entity_id, entity_type, properties=None):
        if properties is None:
            properties = {}
        properties['type'] = entity_type
        self.sst.Vertex(entity_id, entity_type, **properties)

    def add_relationship(self, source_id, target_id, rel_type, weight=1.0):
        self.sst.Edge(source_id, target_id, rel_type, weight)

    def save(self):
        pass

    def load(self):
        pass

    def get_entity_context(self, entity_name, depth=1):
        if depth <= 1:
            orbit = self.sst.GetNodeOrbit(entity_name)
            if not orbit["incoming"] and not orbit["outgoing"]:
                return ""
            lines = [f"Varlık: {entity_name} ({orbit['type']})"]
            for out in orbit["outgoing"]:
                lines.append(f"- {entity_name} --[{out['arrow']}]--> {out['target']}")
            for inc in orbit["incoming"]:
                lines.append(f"- {inc['source']} --[{inc['arrow']}]--> {entity_name}")
            return "\n".join(lines)
        else:
            paths = self.sst.GetFwdPathsAsLinks(entity_name, depth=depth)
            if not paths:
                return ""
            lines = [f"Varlık: {entity_name} ({self.sst.db.vertices.get(entity_name, type='unknown')})"]
            for path in paths:
                orbit = path["orbit"]
                if len(orbit) >= 2:
                    nodes = [n["node"] for n in orbit]
                    arrows = path.get("arrow_sequence", [])
                    arrow_str = arrows[0] if arrows else "ilişkili"
                    lines.append(f"- {' -> '.join(nodes)} [{arrow_str}]")
            return "\n".join(lines)

    def get_all_entities(self):
        return list(self.sst.db.vertices.keys())

    def detect_communities(self):
        if not LEIDEN_AVAILABLE:
            return []
        if len(self.sst.db.vertices) < 2:
            return []

        import networkx as nx
        g = nx.Graph()
        for v in self.sst.db.vertices:
            g.add_node(v)
        for e in self.sst.db.edges:
            g.add_edge(e.source, e.target, weight=e.weight)

        ig_graph = ig.Graph.from_networkx(g)
        partitions = leidenalg.find_partition(ig_graph, leidenalg.ModularityVertexPartition)

        communities = []
        COMMUNITY_PALETTE = [
            "#E91E63", "#9C27B0", "#673AB7", "#3F51B5",
            "#2196F3", "#00BCD4", "#4CAF50", "#FFC107"
        ]

        for i, community in enumerate(partitions):
            members = [ig_graph.vs[v]["_nx_name"] for v in community]
            communities.append({
                "id": i,
                "members": members,
                "size": len(members),
                "color": COMMUNITY_PALETTE[i % len(COMMUNITY_PALETTE)]
            })

        self._communities_cache = communities
        return communities

    def get_stats(self):
        stats = self.sst.GetStats()
        if self._communities_cache is None:
            self.detect_communities()
        return {
            "nodes": stats["vertices"],
            "edges": stats["edges"],
            "density": self._calc_density(),
            "communities": len(self._communities_cache) if self._communities_cache else 0
        }

    def _calc_density(self):
        v = len(self.sst.db.vertices)
        e = len(self.sst.db.edges)
        if v < 2:
            return 0.0
        max_edges = v * (v - 1) / 2
        return e / max_edges if max_edges > 0 else 0.0

    def get_top_entities(self, n=5, metric="degree"):
        if len(self.sst.db.vertices) == 0:
            return []

        if metric == "degree":
            centrality = self._degree_centrality()
        elif metric == "betweenness":
            centrality = self._betweenness_centrality()
        else:
            centrality = self._degree_centrality()

        sorted_entities = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        return [{"entity": e, "score": round(s, 4), "type": self.sst.db.vertices[e].type}
                for e, s in sorted_entities[:n]]

    def _degree_centrality(self):
        scores = {}
        for v in self.sst.db.vertices:
            orbit = self.sst.GetNodeOrbit(v)
            scores[v] = len(orbit["incoming"]) + len(orbit["outgoing"])
        total = max(sum(scores.values()), 1)
        return {k: v / total for k, v in scores.items()}

    def _betweenness_centrality(self):
        scores = {}
        for v in self.sst.db.vertices:
            count = 0
            for e in self.sst.db.edges:
                if e.source == v or e.target == v:
                    count += 1
            scores[v] = count
        total = max(sum(scores.values()), 1)
        return {k: v / total for k, v in scores.items()}

    def get_node_type_counts(self):
        types = [v.type for v in self.sst.db.vertices.values()]
        return dict(Counter(types))

    def get_entity_by_type(self, entity_type):
        return [n for n, v in self.sst.db.vertices.items() if v.type == entity_type]

    def search_entities(self, query, entity_type=None):
        query_lower = query.lower()
        results = []
        for node, vertex in self.sst.db.vertices.items():
            if query_lower in node.lower():
                if entity_type is None or vertex.type == entity_type:
                    orbit = self.sst.GetNodeOrbit(node)
                    results.append({
                        "entity": node,
                        "type": vertex.type,
                        "desc": vertex.properties.get('desc', ''),
                        "neighbors": [o["target"] for o in orbit["outgoing"]] + [i["source"] for i in orbit["incoming"]]
                    })
        return results

    def get_paths_from_entity(self, entity_name, depth=2):
        return self.sst.GetFwdPathsAsLinks(entity_name, depth=depth)

    def get_nc_cone_paths(self, entity_name, depth=2):
        return self.sst.GetEntireNCConePathsAsLinks(entity_name, depth=depth)

    def get_node_orbit(self, entity_name):
        return self.sst.GetNodeOrbit(entity_name)

    @property
    def graph(self):
        class GraphBridge:
            def __init__(sst_db):
                sst_db.edges = sst_db.sst.db.edges
                sst_db.vertices = sst_db.sst.db.vertices

            def nodes(slef):
                return list(sst_db.sst.db.vertices.keys())

            def edges(slef):
                return [(e.source, e.target) for e in sst_db.sst.db.edges]

        return GraphBridge(self)