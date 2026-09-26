from fastapi import FastAPI
from backend.routes import settings, subjects, lessons, reviews, stats

app = FastAPI(title="Kanji SRS")

app.include_router(settings.router, prefix="/api")
app.include_router(subjects.router, prefix="/api")
app.include_router(lessons.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
