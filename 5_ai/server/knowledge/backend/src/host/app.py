"""FastAPI application assembly for the backend host."""

from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..modules.agent_session.service import warm_up_agent
from ..modules.files.api import router as files_router
from ..modules.ontology.api import read_router as ontology_router
from ..shared.logging import SmartLogger
from ..modules.operations.api import router as operations_router, initialize as initialize_operations
from ..modules.ontology.review import router as knowledge_review_router
from ..modules.operations.evidence import router as evidence_router
from ..modules.operations.pipeline import router as pipeline_router
from ..modules.operations.actions import router as actions_router, initialize as initialize_actions
from ..modules.operations.agent import router as manufacturing_agent_router, initialize as initialize_agent_runs, mark_interrupted_runs
from ..modules.ontology.prepare import router as knowledge_prepare_router
from ..modules.ontology.build import router as knowledge_build_router, initialize as initialize_knowledge_builds, mark_interrupted as mark_knowledge_interrupted
from ..modules.operations.thermal_observation import run as observe_temperature
from ..modules.operations.fault_ontology import router as fault_ontology_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up infrastructure used by the application."""

    del app
    SmartLogger.instance().log_startup_status()
    warm_up_agent()
    initialize_operations()
    initialize_actions()
    initialize_agent_runs()
    mark_interrupted_runs()
    initialize_knowledge_builds()
    mark_knowledge_interrupted()
    stop = asyncio.Event()
    observer = asyncio.create_task(observe_temperature(stop))
    try:
        yield
    finally:
        stop.set()
        await observer


def create_app() -> FastAPI:
    """Create the FastAPI application."""

    app = FastAPI(title="AR-100 Manufacturing Assistant", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(ontology_router)
    app.include_router(files_router)
    app.include_router(operations_router)
    app.include_router(knowledge_review_router)
    app.include_router(evidence_router)
    app.include_router(pipeline_router)
    app.include_router(actions_router)
    app.include_router(manufacturing_agent_router)
    app.include_router(knowledge_prepare_router)
    app.include_router(knowledge_build_router)
    app.include_router(fault_ontology_router)
    return app


app = create_app()
