import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.database import Base, engine, SessionLocal
from backend.models import Setting
from backend.routes import settings, subjects, lessons, reviews, stats, levels

app = FastAPI(title="Kanji SRS")

app.include_router(settings.router, prefix="/api")
app.include_router(subjects.router, prefix="/api")
app.include_router(lessons.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(levels.router, prefix="/api")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@app.on_event("startup")
def seed_defaults():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    defaults = {
        "srs_intervals": [0, 14400, 28800, 82800, 169200, 601200, 1206000, 2588400, 10364400, 0],
        "lesson_batch_size": 5,
        "jlpt_gating": True,
        "dependency_gating": True,
        "max_reviews_per_session": None,
    }
    for k, v in defaults.items():
        if not db.query(Setting).filter_by(key=k).first():
            db.add(Setting(key=k, value=json.dumps(v)))
    db.commit()
    db.close()


if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file_path = FRONTEND_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
