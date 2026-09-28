"""Real Postgres round-trip of imported Process GPT HITL, without an LLM.

This verifies infrastructure only, not authority to operate equipment.
"""
import asyncio
import os
from uuid import uuid4
from typing import TypedDict

import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from backend.src.modules.process_runtime.checkpointer import checkpoint_postgres_uri
from backend.src.modules.process_runtime.hitl import _ask_user_impl, extract_interrupt_payload


class State(TypedDict, total=False):
    proposal: str
    decision: str


def graph(saver):
    def review(state):
        answer = _ask_user_impl("대응안을 검토하세요", state["proposal"],
                                [{"label": "approve"}, {"label": "reject"}])
        if answer not in {"approve", "reject"}:
            raise ValueError("Unknown decision; no action authorized")
        return {"decision": answer}
    builder = StateGraph(State)
    builder.add_node("review", review)
    builder.add_edge(START, "review")
    builder.add_edge("review", END)
    return builder.compile(checkpointer=saver)


@pytest.mark.parametrize("decision", ["approve", "reject", "invalid"])
def test_review_survives_new_connection(decision):
    if not os.environ.get("DB_HOST"):
        pytest.skip("Integration test requires a real Postgres DB_HOST")

    async def run():
        uri = checkpoint_postgres_uri()
        config = {"configurable": {"thread_id": f"integration-{uuid4()}"}}
        async with AsyncPostgresSaver.from_conn_string(uri) as saver:
            await saver.setup()
            result = await graph(saver).ainvoke({"proposal": "Integration probe; no equipment command"}, config)
            assert extract_interrupt_payload(result)["question"] == "대응안을 검토하세요"
            assert "decision" not in result
        # Recreate connection and graph: no in-memory checkpoint can satisfy this.
        async with AsyncPostgresSaver.from_conn_string(uri) as saver:
            resumed = graph(saver)
            if decision == "invalid":
                with pytest.raises(ValueError, match="Unknown decision"):
                    await resumed.ainvoke(Command(resume={"answer": decision}), config)
                state = await resumed.aget_state(config)
                assert "decision" not in state.values
            else:
                result = await resumed.ainvoke(Command(resume={"answer": decision}), config)
                assert result["decision"] == decision
                assert not (await resumed.aget_state(config)).next
    asyncio.run(run())
