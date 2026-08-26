"""Aplicación FastAPI: API REST + servido del frontend compilado."""

from fastapi import FastAPI
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from screener.api.routers import favorites, health, pipeline, portfolio, signals
from screener.config import PROJECT_ROOT
from screener.db import init_db

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


def create_app() -> FastAPI:
    init_db()
    app = FastAPI(title="Stock Screener", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(signals.router, prefix="/api")
    app.include_router(portfolio.router, prefix="/api")
    app.include_router(health.router, prefix="/api")
    app.include_router(pipeline.router, prefix="/api")
    app.include_router(favorites.router, prefix="/api")

    if FRONTEND_DIST.exists():
        # El dashboard es una SPA con rutas de cliente (/oportunidades, /salud…).
        # StaticFiles responde 404 a esas rutas: recargar la página o abrir un
        # enlace directo devolvía JSON en vez de la app. El fallback sirve
        # index.html para cualquier ruta que no sea /api ni un fichero real.
        @app.exception_handler(StarletteHTTPException)
        async def spa_fallback(request, exc: StarletteHTTPException):
            if exc.status_code == 404 and not request.url.path.startswith("/api"):
                return FileResponse(FRONTEND_DIST / "index.html")
            # Cualquier otro error mantiene la respuesta JSON estándar: relanzar
            # aquí lo convertiría en un 500.
            return await http_exception_handler(request, exc)

        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app


app = create_app()
