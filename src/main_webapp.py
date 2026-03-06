from __future__ import annotations

"""Entrypoint for the jot-webapp container.

Runs the FastAPI web UI server with uvicorn.
"""

import uvicorn


def run() -> None:
    uvicorn.run(
        "src.webapp.server:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
    )


if __name__ == "__main__":
    run()
