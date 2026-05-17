# -*- coding: utf-8 -*-
import networkx as nx
import json
import os

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
