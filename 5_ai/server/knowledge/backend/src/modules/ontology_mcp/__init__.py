"""Read-only MCP server exposing Ontology Studio search over the Model Context Protocol.

Tools:
  - ontology_query          natural-language question -> answer text + cited source nodes
  - ontology_list_entities  entity "bundle" retrieval by class / schema / criteria / semantics
  - ontology_list_schemas   schema-group catalog with entity counts
  - ontology_get_schema     read the aggregated schema or a single schema group

The surface is strictly read-only: it reuses the studio's existing ontology tools
and the read-only answer agent, and never registers a write or sandbox tool.
"""

from .server import build_server, TOOL_NAMES

__all__ = ["build_server", "TOOL_NAMES"]
