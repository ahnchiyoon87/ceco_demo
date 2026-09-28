# Process GPT runtime components

Source: uengine-oss/process-gpt-deepagents
Revision: 1bf79e04546efe9d660ac2da7af13453837ac4fa
Authorization: company owner/user authorized reuse, modification and branding changes in this thread, 2026-09-21.

Mappings (initial copies unchanged):
- core/chat/hitl.py -> hitl.py
- core/agents/input_builder.py -> input_builder.py
- core/storage/checkpointer.py -> checkpointer.py
- core/llm/mcp.py -> mcp.py

Only invoke documented integrated paths. Some upstream MCP convenience functions
still reference the original core package and Supabase; these are not yet integrated.
Manufacturing approval must require persistent storage and separate action authorization;
the upstream generic human-response tool alone does not grant equipment permissions.
