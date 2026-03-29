"""
Entity retrieval and filtering service.

Supports both legacy Zep-backed graphs and local Graphiti/Neo4j graphs.
"""

import os
import time
import base64
from typing import Dict, Any, List, Optional, Set, Callable, TypeVar
from dataclasses import dataclass, field

import requests
from zep_cloud.client import Zep

from ..config import Config
from ..utils.graph_normalization import (
    canonicalize_entity_name,
    choose_stronger_entity_type,
    infer_entity_type,
    preferred_display_name,
)
from ..utils.logger import get_logger
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges

logger = get_logger('mirofish.zep_entity_reader')

NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "mirofish-neo4j")
NEO4J_HTTP_URL = os.environ.get("NEO4J_HTTP_URL", "http://neo4j:7474")

# Used for generic return type
T = TypeVar('T')


@dataclass
class EntityNode:
    """Entity node data structure"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    # Related edge information
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    # Related other node information
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }
    
    def get_entity_type(self) -> Optional[str]:
        """Get entity type (excluding default Entity label)"""
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        for key in ("entity_type", "type", "category", "kind"):
            value = self.attributes.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None


@dataclass
class FilteredEntities:
    """Filtered entity collection"""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class ZepEntityReader:
    """
    Zep Entity Retrieval and Filtering Service
    
    Main functions:
    1. Read all nodes from the Zep graph
    2. Filter nodes that match predefined entity types (Labels are not only Entity nodes)
    3. Get related edges and associated node information for each entity
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        self.client = Zep(api_key=self.api_key) if self.api_key else None

    def _is_local_graph(self, graph_id: str) -> bool:
        return bool(graph_id and graph_id.startswith("mirofish_"))

    def _require_zep_client(self) -> Zep:
        if self.client is None:
            raise ValueError("ZEP_API_KEY not configured for Zep-backed graph access")
        return self.client

    def _neo4j(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        creds = base64.b64encode(f"{NEO4J_USER}:{NEO4J_PASSWORD}".encode()).decode()
        resp = requests.post(
            f"{NEO4J_HTTP_URL}/db/neo4j/tx/commit",
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={"statements": [{"statement": cypher, "parameters": params or {}}]},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("errors"):
            raise RuntimeError(f"Neo4j error: {payload['errors']}")
        results = payload.get("results", [])
        if not results or not results[0].get("data"):
            return []
        columns = results[0]["columns"]
        return [dict(zip(columns, row["row"])) for row in results[0]["data"]]

    def _entity_type_from_local_node(
        self,
        labels: List[str],
        attributes: Dict[str, Any],
        name: str = "",
        summary: str = "",
    ) -> str:
        return infer_entity_type(labels, attributes, name=name, summary=summary)

    def _merge_duplicate_entities(self, entities: List[EntityNode]) -> List[EntityNode]:
        merged: Dict[str, EntityNode] = {}
        name_sets: Dict[str, set[str]] = {}

        for entity in entities:
            entity_type = entity.get_entity_type() or "Entity"
            canonical_name = canonicalize_entity_name(entity.name)
            merge_key = canonical_name if canonical_name and len(canonical_name) >= 2 else entity.uuid

            existing = merged.get(merge_key)
            if existing is None:
                merged[merge_key] = entity
                name_sets[merge_key] = {entity.name}
                continue

            name_sets[merge_key].add(entity.name)
            stronger_type = choose_stronger_entity_type(existing.get_entity_type() or "Entity", entity_type)
            existing.attributes["entity_type"] = stronger_type
            if stronger_type != "Entity":
                existing.labels = [stronger_type, *[label for label in existing.labels if label != stronger_type]]
            existing.labels = list(dict.fromkeys([*existing.labels, *entity.labels]))
            if len(entity.summary or "") > len(existing.summary or ""):
                existing.summary = entity.summary

            merged_edges = {
                (
                    edge.get("direction"),
                    edge.get("edge_name"),
                    edge.get("fact"),
                    edge.get("source_node_uuid"),
                    edge.get("target_node_uuid"),
                ): edge
                for edge in existing.related_edges
            }
            for edge in entity.related_edges:
                edge_key = (
                    edge.get("direction"),
                    edge.get("edge_name"),
                    edge.get("fact"),
                    edge.get("source_node_uuid"),
                    edge.get("target_node_uuid"),
                )
                merged_edges.setdefault(edge_key, edge)
            existing.related_edges = list(merged_edges.values())

            merged_nodes = {node.get("uuid") or node.get("name"): node for node in existing.related_nodes}
            for node in entity.related_nodes:
                merged_nodes.setdefault(node.get("uuid") or node.get("name"), node)
            existing.related_nodes = list(merged_nodes.values())

        for key, entity in merged.items():
            entity.name = preferred_display_name(name_sets.get(key, {entity.name}))

        return list(merged.values())
    
    def _call_with_retry(
        self, 
        func: Callable[[], T], 
        operation_name: str,
        max_retries: int = 3,
        initial_delay: float = 2.0
    ) -> T:
        """
        Zep API call with retry mechanism
        
        Args:
            func: Function to execute (parameterless lambda or callable)
            operation_name: Operation name, used for logging
            max_retries: Maximum retry attempts (default 3, i.e., try up to 3 times)
            initial_delay: Initial delay in seconds
            
        Returns:
            API call result
        """
        last_exception = None
        delay = initial_delay
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Zep {operation_name} attempt {attempt + 1} failed: {str(e)[:100]}, "
                        f"Retrying after {delay:.1f} seconds..."
                    )
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Zep {operation_name} still failed after {max_retries} attempts: {str(e)}")
        
        raise last_exception
    
    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all nodes of the graph (paginated retrieval)

        Args:
            graph_id: Graph ID

        Returns:
            Node list
        """
        logger.info(f"Retrieving all nodes of graph {graph_id}...")

        if self._is_local_graph(graph_id):
            rows = self._neo4j(
                "MATCH (n:Entity {group_id: $gid}) "
                "RETURN n.uuid AS uuid, coalesce(n.name, '') AS name, labels(n) AS labels, "
                "coalesce(n.summary, '') AS summary LIMIT 5000",
                {"gid": graph_id},
            )
            nodes_data = [
                {
                    "uuid": row.get("uuid", ""),
                    "name": row.get("name", ""),
                    "labels": row.get("labels") or ["Entity"],
                    "summary": row.get("summary", ""),
                    "attributes": {},
                }
                for row in rows
            ]
            logger.info(f"Retrieved {len(nodes_data)} nodes from local Neo4j graph")
            return nodes_data

        nodes = fetch_all_nodes(self._require_zep_client(), graph_id)

        nodes_data = []
        for node in nodes:
            nodes_data.append({
                "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                "name": node.name or "",
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
            })

        logger.info(f"Total {len(nodes_data)} nodes retrieved")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all edges of the graph (paginated retrieval)

        Args:
            graph_id: Graph ID

        Returns:
            Edge List
        """
        logger.info(f"Get graph {graph_id} all edges...")

        if self._is_local_graph(graph_id):
            rows = self._neo4j(
                "MATCH (s:Entity {group_id: $gid})-[r]->(t:Entity {group_id: $gid}) "
                "RETURN coalesce(r.uuid, '') AS uuid, type(r) AS name, coalesce(r.fact, '') AS fact, "
                "s.uuid AS source_node_uuid, t.uuid AS target_node_uuid",
                {"gid": graph_id},
            )
            edges_data = [
                {
                    "uuid": row.get("uuid", ""),
                    "name": row.get("name", ""),
                    "fact": row.get("fact", ""),
                    "source_node_uuid": row.get("source_node_uuid", ""),
                    "target_node_uuid": row.get("target_node_uuid", ""),
                    "attributes": {},
                }
                for row in rows
            ]
            logger.info(f"Retrieved {len(edges_data)} edges from local Neo4j graph")
            return edges_data

        edges = fetch_all_edges(self._require_zep_client(), graph_id)

        edges_data = []
        for edge in edges:
            edges_data.append({
                "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                "name": edge.name or "",
                "fact": edge.fact or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "attributes": edge.attributes or {},
            })

        logger.info(f"Total fetched {len(edges_data)} edges")
        return edges_data
    
    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """
        Get all related edges of specified node (with retry mechanism)
        
        Args:
            node_uuid: Node UUID
            
        Returns:
            Edge List
        """
        try:
            # Use retry mechanism to call Zep API
            edges = self._call_with_retry(
                func=lambda: self._require_zep_client().graph.node.get_entity_edges(node_uuid=node_uuid),
                operation_name=f"Get node edges(node={node_uuid[:8]}...)"
            )
            
            edges_data = []
            for edge in edges:
                edges_data.append({
                    "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                    "name": edge.name or "",
                    "fact": edge.fact or "",
                    "source_node_uuid": edge.source_node_uuid,
                    "target_node_uuid": edge.target_node_uuid,
                    "attributes": edge.attributes or {},
                })
            
            return edges_data
        except Exception as e:
            logger.warning(f"Get node {node_uuid} edges failed: {str(e)}")
            return []
    
    def filter_defined_entities(
        self, 
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True
    ) -> FilteredEntities:
        """
        Filter nodes that match predefined entity types
        
        Filter logic:
        - If a node's Labels contain only "Entity", it means the entity does not match our predefined types, skip
        - If a node's Labels contain tags other than "Entity" and "Node", it means it matches predefined types, keep
        
        Args:
            graph_id: Graph ID
            defined_entity_types: Predefined entity types list (optional, if provided only keep these types)
            enrich_with_edges: Whether to fetch related edges for each entity
            
        Returns:
            FilteredEntities: Filtered entity collection
        """
        logger.info(f"Start filtering graph {graph_id} entities...")
        
        # Get all nodes
        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)
        
        # Get all edges (for subsequent association lookup)
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        
        # Build mapping from node UUID to node data
        node_map = {n["uuid"]: n for n in all_nodes}
        
        # Filter entities that meet conditions
        filtered_entities = []
        entity_types_found = set()
        
        for node in all_nodes:
            labels = node.get("labels", [])
            
            # Legacy Zep graphs rely on custom labels beyond Entity/Node.
            # Local Graphiti graphs may only have the Entity label, so keep those as generic Entity nodes.
            custom_labels = [l for l in labels if l not in ["Entity", "Node"]]
            local_entity_type = self._entity_type_from_local_node(
                labels,
                node.get("attributes", {}),
                name=node.get("name", ""),
                summary=node.get("summary", ""),
            ) if self._is_local_graph(graph_id) else None
            
            if not custom_labels and not local_entity_type:
                # Only default tags, skip
                continue
            
            # If predefined types are specified, check if they match
            if defined_entity_types:
                candidate_labels = custom_labels[:] or ([local_entity_type] if local_entity_type else [])
                matching_labels = [l for l in candidate_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0] if custom_labels else local_entity_type
            
            entity_types_found.add(entity_type)
            
            # Create entity node object
            entity_attributes = dict(node["attributes"] or {})
            if local_entity_type and "entity_type" not in entity_attributes:
                entity_attributes["entity_type"] = local_entity_type

            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=entity_attributes,
            )
            
            # Get related edges and nodes
            if enrich_with_edges:
                related_edges = []
                related_node_uuids = set()
                
                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])
                
                entity.related_edges = related_edges
                
                # Get basic info of related nodes
                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node["uuid"],
                            "name": related_node["name"],
                            "labels": related_node["labels"],
                            "summary": related_node.get("summary", ""),
                        })
                
                entity.related_nodes = related_nodes
            
            filtered_entities.append(entity)

        filtered_entities = self._merge_duplicate_entities(filtered_entities)
        entity_types_found = {entity.get_entity_type() or "Entity" for entity in filtered_entities}

        logger.info(f"Filtering complete: total nodes {total_count}, matching {len(filtered_entities)}, Entity type: {entity_types_found}")
        
        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )
    
    def get_entity_with_context(
        self, 
        graph_id: str, 
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """
        Get a single entity and its full context (edges and related nodes, with retry mechanism)
        
        Args:
            graph_id: Graph ID
            entity_uuid: Entity UUID
            
        Returns:
            EntityNode or None
        """
        try:
            if self._is_local_graph(graph_id):
                node_rows = self._neo4j(
                    "MATCH (n:Entity {group_id: $gid, uuid: $uuid}) "
                    "RETURN n.uuid AS uuid, coalesce(n.name, '') AS name, labels(n) AS labels, "
                    "coalesce(n.summary, '') AS summary",
                    {"gid": graph_id, "uuid": entity_uuid},
                )

                if not node_rows:
                    return None

                base = node_rows[0]
                labels = base.get("labels") or ["Entity"]
                entity_type = self._entity_type_from_local_node(
                    labels,
                    {},
                    name=base.get("name", ""),
                    summary=base.get("summary", ""),
                )
                edge_rows = self._neo4j(
                    "MATCH (n:Entity {group_id: $gid, uuid: $uuid})-[r]-(m:Entity {group_id: $gid}) "
                    "RETURN type(r) AS edge_name, coalesce(r.fact, '') AS fact, "
                    "startNode(r).uuid AS source_node_uuid, endNode(r).uuid AS target_node_uuid, "
                    "m.uuid AS related_uuid, coalesce(m.name, '') AS related_name, "
                    "labels(m) AS related_labels, coalesce(m.summary, '') AS related_summary",
                    {"gid": graph_id, "uuid": entity_uuid},
                )

                related_edges = []
                related_nodes = []
                seen_related = set()

                for edge in edge_rows:
                    is_outgoing = edge.get("source_node_uuid") == entity_uuid
                    related_edges.append({
                        "direction": "outgoing" if is_outgoing else "incoming",
                        "edge_name": edge.get("edge_name", ""),
                        "fact": edge.get("fact", ""),
                        "target_node_uuid": edge.get("target_node_uuid", "") if is_outgoing else None,
                        "source_node_uuid": edge.get("source_node_uuid", "") if not is_outgoing else None,
                    })

                    related_uuid = edge.get("related_uuid", "")
                    if related_uuid and related_uuid not in seen_related:
                        seen_related.add(related_uuid)
                        related_nodes.append({
                            "uuid": related_uuid,
                            "name": edge.get("related_name", ""),
                            "labels": edge.get("related_labels") or ["Entity"],
                            "summary": edge.get("related_summary", ""),
                        })

                return EntityNode(
                    uuid=base.get("uuid", ""),
                    name=base.get("name", ""),
                    labels=labels,
                    summary=base.get("summary", ""),
                    attributes={"entity_type": entity_type},
                    related_edges=related_edges,
                    related_nodes=related_nodes,
                )

            # Use retry mechanism to get node
            node = self._call_with_retry(
                func=lambda: self._require_zep_client().graph.node.get(uuid_=entity_uuid),
                operation_name=f"Get node details(uuid={entity_uuid[:8]}...)"
            )
            
            if not node:
                return None
            
            # Get node's edges
            edges = self.get_node_edges(entity_uuid)
            
            # Get all nodes for related lookup
            all_nodes = self.get_all_nodes(graph_id)
            node_map = {n["uuid"]: n for n in all_nodes}
            
            # Process related edges and nodes
            related_edges = []
            related_node_uuids = set()
            
            for edge in edges:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])
            
            # Get related node information
            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    related_node = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": related_node["uuid"],
                        "name": related_node["name"],
                        "labels": related_node["labels"],
                        "summary": related_node.get("summary", ""),
                    })
            
            return EntityNode(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {},
                related_edges=related_edges,
                related_nodes=related_nodes,
            )
            
        except Exception as e:
            logger.error(f"Get entity {entity_uuid} failed: {str(e)}")
            return None
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """
        Get all entities of specified type
        
        Args:
            graph_id: Graph ID
            entity_type: Entity type (e.g., "Student", "PublicFigure", etc.)
            enrich_with_edges: Whether to get related edge information
            
        Returns:
            Entity list
        """
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities
