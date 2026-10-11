"""Router registry. `create_app()` includes these in order; append new areas (e.g. `insights`) before `static`,
whose SPA catch-all must stay last."""

from fastapi import APIRouter

from api.routers import audit_feed, briefing, cars, definition, document, evidence, markets, meta_state, prioritize, process, queue, requirements, scan, static, structure, usage

ROUTERS: list[APIRouter] = [
    meta_state.router,
    briefing.router,
    queue.router,
    requirements.router,
    cars.router,
    markets.router,
    evidence.router,
    process.router,
    scan.router,
    structure.router,
    definition.router,
    prioritize.router,
    document.router,
    audit_feed.router,
    usage.router,
]

# Always included last by create_app(): /models and the SPA catch-all.
STATIC_ROUTER: APIRouter = static.router
