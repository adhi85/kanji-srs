from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from backend.database import Base, engine
from backend.routes import settings, subjects, lessons, reviews, stats, levels, extra_study, auth


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Kanji SRS", lifespan=lifespan)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(subjects.router, prefix="/api")
app.include_router(lessons.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(levels.router, prefix="/api")
app.include_router(extra_study.router, prefix="/api")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file_path = FRONTEND_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
