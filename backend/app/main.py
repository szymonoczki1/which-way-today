import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import init_db
from app.routers import geocode, routes, trips

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Which Way Today? API", lifespan=lifespan)

    # Registered before CORSMiddleware so CORS wraps it (last added = outermost).
    # An @app.exception_handler(Exception) would not work: Starlette runs it in
    # ServerErrorMiddleware, outside CORS, so the browser would block the 500 and
    # the frontend would report "could not reach the server" instead.
    @app.middleware("http")
    async def unhandled_errors_as_json(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unhandled error on %s %s", request.method, request.url.path)
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(trips.router)
    app.include_router(geocode.router)
    app.include_router(routes.router)

    return app


app = create_app()
