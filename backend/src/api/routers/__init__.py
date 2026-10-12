"""Router registry. `create_app()` includes these in order; append new areas (e.g. `insights`) before `static`,
whose SPA catch-all must stay last."""

from fastapi import APIRouter

from api.routers import agents, audit_feed, definition, document, prioritize, scan, settings, static, structure, usage

ROUTERS: list[APIRouter] = [
    scan.router,
    structure.router,
    definition.router,
    prioritize.router,
    document.router,
    audit_feed.router,
    usage.router,
    settings.router,
    agents.router,
]

# Always included last by create_app(): /models and the SPA catch-all.
STATIC_ROUTER: APIRouter = static.router
