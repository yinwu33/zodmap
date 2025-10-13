from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router


app = FastAPI(
    title="ZodMap API",
    description="REST API exposing driving log data for the ADAS visualisation frontend.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


__all__ = ["app"]
