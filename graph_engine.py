# -*- coding: utf-8 -*-
import networkx as nx
import json
import os
from collections import Counter

try:
    import igraph as ig
    import leidenalg
    LEIDEN_AVAILABLE = True
except ImportError:
    LEIDEN_AVAILABLE = False

class GraphEngine:
    """
    GraphRAG'in Topluluk özetleri ve LLM Wiki'nin graf altyapısını yönetir.
    Verileri 'workspace/graph.json' dosyasına kaydeder.
    """
    def __init__(self, storage_path="workspace/graph.json"):
        self.storage_path = storage_path
        self.graph = nx.Graph()
        self.load()

    def add_entity(self, entity_id, entity_type, properties=None):
        if properties is None: properties = {}
        properties['type'] = entity_type
        self.graph.add_node(entity_id, **properties)

    def add_relationship(self, source_id, target_id, rel_type, weight=1.0):
        self.graph.add_edge(source_id, target_id, weight=weight, type=rel_type)

    def save(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        data = nx.node_link_data(self.graph)
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.graph = nx.node_link_graph(data)
            except Exception as e:
                print(f"Graf yükleme hatası: {e}")
                self.graph = nx.Graph()

    def get_entity_context(self, entity_name, depth=1):
        """Bir varlığın komşularını ve ilişkilerini metin olarak döndürür."""
        if entity_name not in self.graph:
            return ""
        
        context = [f"Varlık: {entity_name} ({self.graph.nodes[entity_name].get('type', 'Bilinmiyor')})"]
        neighbors = list(self.graph.neighbors(entity_name))
        
        for n in neighbors:
            rel_type = self.graph[entity_name][n].get('type', 'ilişkili')
            context.append(f"- {entity_name} --[{rel_type}]--> {n}")
            
        return "\n".join(context)

    def get_all_entities(self):
        return list(self.graph.nodes)

    def detect_communities(self):
        if not LEIDEN_AVAILABLE:
            return []
        if len(self.graph.nodes) < 2:
            return []
        
        ig_graph = ig.Graph.from_networkx(self.graph)
        partitions = leidenalg.find_partition(
            ig_graph, leidenalg.ModularityVertexPartition
        )
        
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
        
        communities_path = os.path.join(os.path.dirname(self.storage_path), "communities.json")
        with open(communities_path, 'w', encoding='utf-8') as f:
            json.dump(communities, f, ensure_ascii=False, indent=2)
        
        return communities

    def get_stats(self):
        if len(self.graph.nodes) == 0:
            return {"nodes": 0, "edges": 0, "density": 0, "communities": 0}
        
        return {
            "nodes": len(self.graph.nodes),
            "edges": len(self.graph.edges),
            "density": nx.density(self.graph),
            "communities": len(self.detect_communities()) if LEIDEN_AVAILABLE else 0
        }

    def get_top_entities(self, n=5, metric="degree"):
        if len(self.graph.nodes) == 0:
            return []
        
        if metric == "degree":
            centrality = nx.degree_centrality(self.graph)
        elif metric == "betweenness":
            centrality = nx.betweenness_centrality(self.graph)
        else:
            centrality = nx.degree_centrality(self.graph)
        
        sorted_entities = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        return [{"entity": e, "score": round(s, 4), "type": self.graph.nodes[e].get('type', 'unknown')}
                for e, s in sorted_entities[:n]]

    def get_node_type_counts(self):
        types = [self.graph.nodes[n].get('type', 'unknown') for n in self.graph.nodes]
        return dict(Counter(types))

    def get_entity_by_type(self, entity_type):
        return [n for n in self.graph.nodes if self.graph.nodes[n].get('type') == entity_type]

    def search_entities(self, query, entity_type=None):
        query_lower = query.lower()
        results = []
        for node in self.graph.nodes:
            if query_lower in node.lower():
                if entity_type is None or self.graph.nodes[node].get('type') == entity_type:
                    results.append({
                        "entity": node,
                        "type": self.graph.nodes[node].get('type', 'unknown'),
                        "desc": self.graph.nodes[node].get('desc', ''),
                        "neighbors": list(self.graph.neighbors(node))
                    })
        return results
