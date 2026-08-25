"""Backward-compatible entry point for the regulation HTTP interface.

The actual FastAPI transport lives in :mod:`zhiyan_legal.interfaces`.
"""

from __future__ import annotations

from .interfaces.http_regulation import (
    api_check,
    api_diff,
    api_diff_all,
    api_history,
    api_search,
    api_status,
    api_sync,
    api_tracked,
    api_tracked_add,
    api_tracked_remove,
    app,
    get_tracker,
)

__all__ = [
    "app", "get_tracker", "api_status", "api_sync", "api_check",
    "api_tracked", "api_tracked_add", "api_tracked_remove", "api_history",
    "api_search", "api_diff", "api_diff_all",
]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "zhiyan_legal.interfaces.http_regulation:app",
        host="127.0.0.1",
        port=7850,
        reload=True,
    )
