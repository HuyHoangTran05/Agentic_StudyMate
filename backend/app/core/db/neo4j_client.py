"""
Neo4j client for GraphRAG ingestion.

Stores extracted entity triplets as (:Entity)-[:RELATION {chunk_id}]->(:Entity)
relationships. The relationship type is sanitized before it is interpolated
into Cypher because Neo4j does not allow relationship types as parameters.
"""

import re

from app.config import get_settings


class Neo4jClient:
    """Async Neo4j driver wrapper for knowledge graph writes."""

    def __init__(self):
        self._settings = get_settings()
        self._driver = None

    def _is_configured(self) -> bool:
        return bool(
            self._settings.NEO4J_URI
            and self._settings.NEO4J_USER
            and self._settings.NEO4J_PASSWORD
        )

    def _get_driver(self):
        """Get or create the Neo4j async driver."""
        if not self._is_configured():
            raise RuntimeError(
                "Neo4j is not configured. Set NEO4J_URI, NEO4J_USER, "
                "and NEO4J_PASSWORD in your .env file."
            )

        if self._driver is None:
            from neo4j import AsyncGraphDatabase

            self._driver = AsyncGraphDatabase.driver(
                self._settings.NEO4J_URI,
                auth=(self._settings.NEO4J_USER, self._settings.NEO4J_PASSWORD),
            )
        return self._driver

    @staticmethod
    def _sanitize_relation_type(relation: str) -> str:
        """
        Convert an LLM relation string into a valid Neo4j relationship type.

        Examples:
            "manages" -> "MANAGES"
            "part of" -> "PART_OF"
        """
        relation_type = re.sub(r"[^0-9A-Za-z_]+", "_", relation.strip())
        relation_type = re.sub(r"_+", "_", relation_type).strip("_").upper()

        if not relation_type:
            return "RELATED_TO"
        if relation_type[0].isdigit():
            relation_type = f"REL_{relation_type}"
        return relation_type

    @staticmethod
    def _clean_entity_name(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    async def verify_connection(self) -> None:
        """Verify that Neo4j is reachable with the configured credentials."""
        driver = self._get_driver()
        await driver.verify_connectivity()

    async def ingest_triplets(
        self,
        triplets: list[dict[str, str]],
        chunk_id: str,
    ) -> int:
        """
        Merge extracted triplets into Neo4j and tag each relationship by chunk.

        Args:
            triplets: [{"source": "...", "relation": "...", "target": "..."}]
            chunk_id: SQLite chunk ID that produced the relationship

        Returns:
            Number of triplets submitted to Neo4j.
        """
        if not triplets:
            return 0

        driver = self._get_driver()
        submitted = 0

        async with driver.session() as session:
            for triplet in triplets:
                source = self._clean_entity_name(triplet.get("source", ""))
                target = self._clean_entity_name(triplet.get("target", ""))
                relation = self._sanitize_relation_type(triplet.get("relation", ""))

                if not source or not target:
                    continue

                query = f"""
                MERGE (source:Entity {{name: $source}})
                MERGE (target:Entity {{name: $target}})
                MERGE (source)-[relationship:{relation} {{chunk_id: $chunk_id}}]->(target)
                SET relationship.source = $source,
                    relationship.target = $target,
                    relationship.relation = $original_relation
                RETURN id(relationship) AS relationship_id
                """
                await session.execute_write(
                    self._run_write,
                    query,
                    {
                        "source": source,
                        "target": target,
                        "original_relation": triplet.get("relation", relation),
                        "chunk_id": chunk_id,
                    },
                )
                submitted += 1

        return submitted

    @staticmethod
    async def _run_write(tx, query: str, parameters: dict):
        result = await tx.run(query, parameters)
        await result.consume()

    async def close(self) -> None:
        """Close the underlying Neo4j driver."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None


_neo4j_client: Neo4jClient | None = None


def get_neo4j_client() -> Neo4jClient:
    """Get or create the singleton Neo4j client."""
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient()
    return _neo4j_client


async def close_neo4j_client() -> None:
    """Close the singleton Neo4j client if it was initialized."""
    global _neo4j_client
    if _neo4j_client is not None:
        await _neo4j_client.close()
        _neo4j_client = None
