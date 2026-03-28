"""
Graphiti-based Graph Construction Service
Uses graphiti_core Python library directly — no REST service, no rate limits.

Stack:
  - graphiti_core → entity/relationship extraction via LLM (qwen3.5:4b via Ollama)
  - Neo4j (bolt://neo4j:7687) → graph storage
  - Neo4j HTTP API (http://neo4j:7474) → node/edge listing for frontend
"""

import os
import uuid
import time
import base64
import threading
import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, get_origin
from dataclasses import dataclass

import requests as _requests
import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

try:
    from graphiti_core.llm_client.client import LLMClient
except Exception:  # pragma: no cover - local non-Graphiti environments
    class LLMClient:  # type: ignore[no-redef]
        def __init__(self, config=None, cache: bool = False):
            self.config = config
            self.model = getattr(config, "model", None)
            self.small_model = getattr(config, "small_model", None)
            self.temperature = getattr(config, "temperature", 0)
            self.max_tokens = getattr(config, "max_tokens", 2048)

from ..utils.logger import get_logger
from ..models.task import TaskManager, TaskStatus
from .text_processor import TextProcessor

logger = get_logger('mirofish.graphiti_builder')

# ── connection config ─────────────────────────────────────────────────────────
NEO4J_BOLT_URI  = os.environ.get("NEO4J_URI",      "bolt://neo4j:7687")
NEO4J_USER      = os.environ.get("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD  = os.environ.get("NEO4J_PASSWORD", "mirofish-neo4j")
NEO4J_HTTP_URL  = os.environ.get("NEO4J_HTTP_URL", "http://neo4j:7474")
LLM_BASE_URL    = os.environ.get("LLM_BASE_URL",   "http://host.docker.internal:11434/v1")
LLM_API_KEY     = os.environ.get("LLM_API_KEY",    "ollama")
GRAPHITI_BASE_URL = os.environ.get("GRAPHITI_BASE_URL", LLM_BASE_URL)
GRAPHITI_API_KEY = os.environ.get("GRAPHITI_API_KEY", LLM_API_KEY)
GRAPHITI_EMBED_BASE_URL = os.environ.get("GRAPHITI_EMBED_BASE_URL", LLM_BASE_URL)
GRAPHITI_EMBED_API_KEY = os.environ.get("GRAPHITI_EMBED_API_KEY", LLM_API_KEY)
GRAPHITI_MODEL  = os.environ.get("GRAPHITI_MODEL_NAME") or os.environ.get("LLM_MODEL_NAME", "qwen3.5:4b")
EMBED_MODEL     = os.environ.get("GRAPHITI_EMBED_MODEL_NAME", "nomic-embed-text:latest")
GRAPHITI_INIT_TIMEOUT_SECONDS = int(os.environ.get("GRAPHITI_INIT_TIMEOUT_SECONDS", "30"))
GRAPHITI_EPISODE_TIMEOUT_SECONDS = int(os.environ.get("GRAPHITI_EPISODE_TIMEOUT_SECONDS", "90"))


class TolerantOpenAIClient(LLMClient):
    """
    OpenAI-compatible Graphiti client that tolerates non-OpenAI structured output behavior.

    Ollama's OpenAI-compatible endpoints may return fenced JSON, prose plus JSON, or a top-level
    list instead of the exact object shape Graphiti requested. This client normalizes those
    outputs locally before Pydantic validation.
    """

    MAX_RETRIES = 2

    def __init__(self, config=None, cache: bool = False, client=None, max_tokens: int = 2048):
        from graphiti_core.llm_client import LLMConfig

        if cache:
            raise NotImplementedError("Caching is not implemented for OpenAI")

        if config is None:
            config = LLMConfig()

        super().__init__(config, cache)
        self.max_tokens = max_tokens
        self.client = client or AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)

    def _clean_input(self, value: str) -> str:
        cleaned = value.encode("utf-8", errors="ignore").decode("utf-8")
        for char in "\u200b\u200c\u200d\ufeff\u2060":
            cleaned = cleaned.replace(char, "")
        return "".join(char for char in cleaned if ord(char) >= 32 or char in "\n\r\t")

    def _normalize_json_for_model(
        self, payload: Any, response_model: type[BaseModel] | None
    ) -> Any:
        if response_model is None:
            return payload

        model_fields = getattr(response_model, "model_fields", {})
        response_field_names = set(model_fields.keys())

        if isinstance(payload, dict) and "properties" in payload and isinstance(payload["properties"], dict):
            inner_payload = payload["properties"]
            if response_field_names and response_field_names.issubset(set(inner_payload.keys())):
                logger.warning(
                    "Graphiti model %s returned schema-style properties wrapper for %s; unwrapping payload",
                    self.model,
                    response_model.__name__,
                )
                payload = {field_name: inner_payload[field_name] for field_name in response_field_names}

        if len(model_fields) == 1:
            field_name, field_info = next(iter(model_fields.items()))
            annotation = getattr(field_info, "annotation", None)
            if get_origin(annotation) is list:
                item_model = None
                item_args = getattr(annotation, "__args__", ())
                if item_args:
                    candidate = item_args[0]
                    if isinstance(candidate, type) and issubclass(candidate, BaseModel):
                        item_model = candidate

                if isinstance(payload, list):
                    logger.warning(
                        "Graphiti model %s returned a top-level list; wrapping into field %s",
                        self.model,
                        field_name,
                    )
                    return {field_name: payload}

                if isinstance(payload, dict):
                    if field_name in payload and isinstance(payload[field_name], dict):
                        field_payload = payload[field_name]
                        if (
                            item_model is not None
                            and "properties" in field_payload
                            and isinstance(field_payload["properties"], dict)
                        ):
                            item_fields = set(getattr(item_model, "model_fields", {}).keys())
                            inner_payload = field_payload["properties"]
                            if item_fields and item_fields.issubset(set(inner_payload.keys())):
                                logger.warning(
                                    "Graphiti model %s returned schema-style properties wrapper inside %s; unwrapping item payload",
                                    self.model,
                                    field_name,
                                )
                                payload = dict(payload)
                                payload[field_name] = {
                                    item_field: inner_payload[item_field] for item_field in item_fields
                                }

                    if field_name in payload and isinstance(payload[field_name], dict):
                        logger.warning(
                            "Graphiti model %s returned dict for list field %s; wrapping singleton item",
                            self.model,
                            field_name,
                        )
                        payload = dict(payload)
                        payload[field_name] = [payload[field_name]]
                        return payload

                    if item_model is not None:
                        item_fields = set(getattr(item_model, "model_fields", {}).keys())
                        payload_keys = set(payload.keys())
                        if payload_keys and payload_keys.issubset(item_fields):
                            logger.warning(
                                "Graphiti model %s returned singleton object for %s; wrapping into %s list",
                                self.model,
                                response_model.__name__,
                                field_name,
                            )
                            return {field_name: [payload]}

                        if "properties" in payload and isinstance(payload["properties"], dict):
                            inner_payload = payload["properties"]
                            if item_fields and item_fields.issubset(set(inner_payload.keys())):
                                logger.warning(
                                    "Graphiti model %s returned schema-style properties wrapper for %s item; unwrapping and wrapping into %s list",
                                    self.model,
                                    response_model.__name__,
                                    field_name,
                                )
                                return {
                                    field_name: [
                                        {item_field: inner_payload[item_field] for item_field in item_fields}
                                    ]
                                }

        return payload

    def _extract_json_payload(self, content: str) -> Any:
        text = (content or "").strip()
        if not text:
            raise ValueError("Model returned empty content")

        fenced_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if fenced_match:
            text = fenced_match.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        for marker in ("{", "["):
            start = text.find(marker)
            while start != -1:
                try:
                    payload, _ = decoder.raw_decode(text[start:])
                    return payload
                except json.JSONDecodeError:
                    start = text.find(marker, start + 1)

        raise ValueError(f"Could not extract JSON from model response: {text[:400]}")

    async def _generate_response(
        self,
        messages,
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 2048,
        model_size=None,
    ) -> dict[str, Any]:
        openai_messages: list[ChatCompletionMessageParam] = []
        for message in messages:
            message.content = self._clean_input(message.content)
            if message.role in ("user", "system"):
                openai_messages.append({"role": message.role, "content": message.content})

        model = self.small_model if str(model_size).endswith("small") and self.small_model else self.model
        try:
            request_kwargs = {
                "model": model,
                "messages": openai_messages,
                "temperature": self.temperature,
                "max_tokens": max_tokens or self.max_tokens,
            }

            response = await self.client.chat.completions.create(
                **request_kwargs,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
            if not str(content).strip():
                logger.warning(
                    "Graphiti model %s returned empty content in json_object mode; retrying without response_format",
                    model,
                )
                response = await self.client.chat.completions.create(**request_kwargs)
                content = response.choices[0].message.content or ""
            payload = self._extract_json_payload(content)
            payload = self._normalize_json_for_model(payload, response_model)
            if response_model is not None:
                return response_model.model_validate(payload).model_dump()
            if isinstance(payload, dict):
                return payload
            return {"result": payload}
        except openai.RateLimitError as exc:
            from graphiti_core.llm_client.errors import RateLimitError

            raise RateLimitError from exc
        except Exception as exc:
            logger.error("Error in generating LLM response: %s", exc)
            raise

    async def generate_response(
        self,
        messages,
        response_model: type[BaseModel] | None = None,
        max_tokens: int | None = None,
        model_size=None,
    ) -> dict[str, Any]:
        from graphiti_core.llm_client.client import MULTILINGUAL_EXTRACTION_RESPONSES
        from graphiti_core.llm_client.errors import RefusalError

        if max_tokens is None:
            max_tokens = self.max_tokens

        retry_count = 0
        last_error = None

        if response_model is not None:
            serialized_model = json.dumps(response_model.model_json_schema())
            messages[-1].content += (
                "\n\nReturn only valid JSON."
                "\nDo not include markdown code fences."
                "\nDo not include prose before or after the JSON."
                f"\nThe JSON must match this schema exactly:\n{serialized_model}"
            )

        messages[0].content += MULTILINGUAL_EXTRACTION_RESPONSES

        while retry_count <= self.MAX_RETRIES:
            try:
                return await self._generate_response(
                    messages,
                    response_model=response_model,
                    max_tokens=max_tokens,
                    model_size=model_size,
                )
            except (RefusalError, openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError):
                raise
            except Exception as exc:
                last_error = exc
                if retry_count >= self.MAX_RETRIES:
                    logger.error("Max retries (%s) exceeded. Last error: %s", self.MAX_RETRIES, exc)
                    raise

                retry_count += 1
                messages.append(
                    type(messages[-1])(
                        role="user",
                        content=(
                            "The previous response was invalid. "
                            f"Error type: {exc.__class__.__name__}. "
                            f"Error details: {str(exc)}. "
                            "Respond again with only valid JSON matching the required schema."
                        ),
                    )
                )
                logger.warning(
                    "Retrying after application error (attempt %s/%s): %s",
                    retry_count,
                    self.MAX_RETRIES,
                    exc,
                )

        raise last_error or Exception("Max retries exceeded with no specific error")


def _get_graphiti_llm_config():
    """Resolve Graphiti LLM config from the active ModelRegistry selection."""
    from .model_registry import ModelRegistry
    sel = ModelRegistry().get_active()
    return sel.base_url, sel.api_key, sel.model_name


def _make_graphiti():
    """Create a configured graphiti_core.Graphiti instance."""
    from graphiti_core import Graphiti
    from graphiti_core.llm_client import LLMConfig
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
    from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

    _base_url, _api_key, _model = _get_graphiti_llm_config()
    llm_config = LLMConfig(
        api_key=_api_key,
        base_url=_base_url,
        model=_model,
        small_model=_model,
    )
    llm = TolerantOpenAIClient(config=llm_config)
    embedder = OpenAIEmbedder(config=OpenAIEmbedderConfig(
        api_key=GRAPHITI_EMBED_API_KEY,
        base_url=GRAPHITI_EMBED_BASE_URL,
        embedding_model=EMBED_MODEL,
    ))
    cross_encoder = OpenAIRerankerClient(config=llm_config)
    return Graphiti(
        uri=NEO4J_BOLT_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
        llm_client=llm,
        embedder=embedder,
        cross_encoder=cross_encoder,
    )


def _run_async(coro):
    """Run an async coroutine from a synchronous (thread) context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@dataclass
class GraphInfo:
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphitiBuilderService:
    """Graph builder using graphiti_core + Neo4j directly. No cloud, no rate limits."""

    def __init__(self):
        self.task_manager = TaskManager()

    # ── Neo4j HTTP helper ─────────────────────────────────────────────────────

    def _neo4j(self, cypher: str, params: dict = None) -> List[Dict[str, Any]]:
        creds = base64.b64encode(f"{NEO4J_USER}:{NEO4J_PASSWORD}".encode()).decode()
        resp = _requests.post(
            f"{NEO4J_HTTP_URL}/db/neo4j/tx/commit",
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={"statements": [{"statement": cypher, "parameters": params or {}}]},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errors"):
            raise RuntimeError(f"Neo4j error: {data['errors']}")
        results = data.get("results", [{}])
        if not results or not results[0].get("data"):
            return []
        columns = results[0]["columns"]
        return [dict(zip(columns, row["row"])) for row in results[0]["data"]]

    # ── async graph operations ────────────────────────────────────────────────

    async def _async_add_episodes(self, graph_id: str, chunks: List[str], progress_callback=None):
        """Add all chunks as episodes. Runs inside a background thread event loop."""
        from graphiti_core.nodes import EpisodeType

        g = _make_graphiti()
        try:
            try:
                await asyncio.wait_for(
                    g.build_indices_and_constraints(),
                    timeout=GRAPHITI_INIT_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError as exc:
                _bu, _ak, _mn = _get_graphiti_llm_config()
                raise RuntimeError(
                    f"Graphiti initialization timed out after {GRAPHITI_INIT_TIMEOUT_SECONDS}s "
                    f"(model={_mn}, base_url={_bu})"
                ) from exc
            total = len(chunks)
            now = datetime.now(timezone.utc)
            for i, chunk in enumerate(chunks):
                if progress_callback:
                    progress_callback(
                        f"Processing chunk {i + 1}/{total}...",
                        (i + 1) / total,
                    )
                try:
                    await asyncio.wait_for(
                        g.add_episode(
                            group_id=graph_id,
                            name=f"chunk_{i}",
                            episode_body=chunk,
                            reference_time=now,
                            source=EpisodeType.text,
                            source_description="MiroFish document",
                        ),
                        timeout=GRAPHITI_EPISODE_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError as exc:
                    raise RuntimeError(
                        f"Chunk {i + 1}/{total} timed out after "
                        f"{GRAPHITI_EPISODE_TIMEOUT_SECONDS}s "
                        f"(model={_get_graphiti_llm_config()[2]}, base_url={_get_graphiti_llm_config()[0]})"
                    ) from exc
                logger.info(f"[{graph_id}] Episode {i + 1}/{total} ingested")
        finally:
            await g.close()

    async def _async_search(self, graph_id: str, query: str, limit: int) -> Dict[str, Any]:
        g = _make_graphiti()
        try:
            results = await g.search(query, group_ids=[graph_id], num_results=limit)
            facts = []
            edges = []
            for edge in results:
                fact = getattr(edge, 'fact', '') or ''
                if fact:
                    facts.append(fact)
                edges.append({
                    "uuid": getattr(edge, 'uuid', ''),
                    "name": getattr(edge, 'name', ''),
                    "fact": fact,
                    "source_node_uuid": getattr(edge, 'source_node_uuid', ''),
                    "target_node_uuid": getattr(edge, 'target_node_uuid', ''),
                })
            return {"facts": facts, "edges": edges, "nodes": [], "total_count": len(facts)}
        finally:
            await g.close()

    # ── public API ────────────────────────────────────────────────────────────

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3,
    ) -> str:
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={"graph_name": graph_name, "chunk_size": chunk_size, "text_length": len(text)},
        )
        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap),
            daemon=True,
        )
        thread.start()
        return task_id

    def _build_graph_worker(self, task_id, text, ontology, graph_name, chunk_size, chunk_overlap):
        try:
            self.task_manager.update_task(
                task_id, status=TaskStatus.PROCESSING, progress=5,
                message="Starting graph build (graphiti_core + Neo4j)..."
            )

            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(task_id, progress=10, message=f"Graph ID: {graph_id}")
            self.task_manager.update_task(task_id, progress=15, message="Ontology skipped (graphiti auto-extracts)")

            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total = len(chunks)
            self.task_manager.update_task(task_id, progress=20, message=f"Text split into {total} chunks")

            def progress_cb(msg, ratio):
                self.task_manager.update_task(task_id, progress=20 + int(ratio * 65), message=msg)

            # Run the async episode ingestion in this thread's own event loop
            _run_async(self._async_add_episodes(graph_id, chunks, progress_cb))

            self.task_manager.update_task(task_id, progress=90, message="Retrieving graph info...")
            try:
                graph_info = self._get_graph_info(graph_id)
                graph_info_dict = graph_info.to_dict()
            except Exception as e:
                logger.warning(f"Graph info query failed: {e}")
                graph_info_dict = {"graph_id": graph_id, "node_count": 0, "edge_count": 0, "entity_types": []}

            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info_dict,
                "chunks_processed": total,
            })

        except Exception as e:
            import traceback
            self.task_manager.fail_task(task_id, f"{str(e)}\n{traceback.format_exc()}")

    def create_graph(self, name: str) -> str:
        return f"mirofish_{uuid.uuid4().hex[:16]}"

    def add_text_batches(self, graph_id, chunks, batch_size=3, progress_callback=None) -> list:
        """Synchronous wrapper — used from api/graph.py build_task."""
        _run_async(self._async_add_episodes(graph_id, chunks, progress_callback))
        return []

    def _wait_for_processing(self, graph_id, expected_chunks, progress_callback=None, timeout=60):
        """No-op — graphiti_core processes synchronously in add_text_batches."""
        if progress_callback:
            progress_callback("Processing complete", 1.0)

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        try:
            node_rows = self._neo4j(
                "MATCH (n:Entity {group_id: $gid}) RETURN count(n) AS cnt", {"gid": graph_id}
            )
            edge_rows = self._neo4j(
                "MATCH (s:Entity {group_id: $gid})-[r]->(t:Entity {group_id: $gid}) RETURN count(r) AS cnt",
                {"gid": graph_id},
            )
            type_rows = self._neo4j(
                "MATCH (n:Entity {group_id: $gid}) RETURN DISTINCT labels(n) AS lbls LIMIT 50",
                {"gid": graph_id},
            )
            node_count = node_rows[0]["cnt"] if node_rows else 0
            edge_count = edge_rows[0]["cnt"] if edge_rows else 0
            entity_types = list({
                lbl for row in type_rows for lbl in (row.get("lbls") or [])
                if lbl not in ("Entity", "Node")
            })
        except Exception as e:
            logger.warning(f"Neo4j graph info query failed: {e}")
            node_count, edge_count, entity_types = 0, 0, []

        return GraphInfo(graph_id=graph_id, node_count=node_count, edge_count=edge_count, entity_types=entity_types)

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        try:
            node_rows = self._neo4j(
                "MATCH (n:Entity {group_id: $gid}) "
                "RETURN n.uuid AS uuid, n.name AS name, labels(n) AS labels, n.summary AS summary LIMIT 500",
                {"gid": graph_id},
            )
            edge_rows = self._neo4j(
                "MATCH (s:Entity {group_id: $gid})-[r]->(t:Entity {group_id: $gid}) "
                "RETURN r.uuid AS uuid, type(r) AS name, r.fact AS fact, "
                "s.uuid AS src, t.uuid AS tgt, s.name AS src_name, t.name AS tgt_name LIMIT 1000",
                {"gid": graph_id},
            )
        except Exception as e:
            logger.warning(f"Neo4j graph data query failed: {e}")
            node_rows, edge_rows = [], []

        nodes_data = [
            {
                "uuid": r.get("uuid", ""),
                "name": r.get("name", ""),
                "labels": [l for l in (r.get("labels") or []) if l != "Entity"],
                "summary": r.get("summary", ""),
                "attributes": {},
                "created_at": None,
            }
            for r in node_rows
        ]
        edges_data = [
            {
                "uuid": r.get("uuid", ""),
                "name": r.get("name", ""),
                "fact": r.get("fact", ""),
                "fact_type": r.get("name", ""),
                "source_node_uuid": r.get("src", ""),
                "target_node_uuid": r.get("tgt", ""),
                "source_node_name": r.get("src_name", ""),
                "target_node_name": r.get("tgt_name", ""),
                "attributes": {},
                "created_at": None,
                "valid_at": None,
                "invalid_at": None,
                "expired_at": None,
                "episodes": [],
            }
            for r in edge_rows
        ]
        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
        }

    def delete_graph(self, graph_id: str):
        try:
            async def _delete():
                g = _make_graphiti()
                try:
                    from graphiti_core.nodes import EntityNode, EpisodicNode
                    from graphiti_core.edges import EntityEdge
                    from graphiti_core.errors import GroupsEdgesNotFoundError
                    try:
                        edges = await EntityEdge.get_by_group_ids(g.driver, [graph_id])
                    except GroupsEdgesNotFoundError:
                        edges = []
                    nodes = await EntityNode.get_by_group_ids(g.driver, [graph_id])
                    episodes = await EpisodicNode.get_by_group_ids(g.driver, [graph_id])
                    for e in edges:
                        await e.delete(g.driver)
                    for n in nodes:
                        await n.delete(g.driver)
                    for ep in episodes:
                        await ep.delete(g.driver)
                finally:
                    await g.close()
            _run_async(_delete())
            logger.info(f"Deleted graph: {graph_id}")
        except Exception as e:
            logger.warning(f"Delete graph failed: {e}")

    def search_graph(self, graph_id: str, query: str, limit: int = 10) -> Dict[str, Any]:
        try:
            return _run_async(self._async_search(graph_id, query, limit))
        except Exception as e:
            logger.warning(f"Graphiti search failed: {e}")
            return {"facts": [], "edges": [], "nodes": [], "total_count": 0}
