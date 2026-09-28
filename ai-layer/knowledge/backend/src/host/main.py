"""Command-line entrypoint for the backend service."""

from __future__ import annotations

import uvicorn

from .app import app
from ..shared.kernel.settings import get_settings


def main() -> None:
    """Run the FastAPI app with configured host and port."""

    settings = get_settings()
    uvicorn.run(app, host=settings.backend_host, port=settings.backend_port)


if __name__ == "__main__":
    main()
