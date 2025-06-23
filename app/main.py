# app/main.py
from fastapi import FastAPI, Response
from contextlib import asynccontextmanager
from app.db.database import connect_to_mongo, close_mongo_connection
from app.api.whatsapp import router as whatsapp_router
from app.core.logging_config import log


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🚀 LAUNCH: Starting Vyayamam application...")
    await connect_to_mongo()
    yield
    log.info("🛑 SHUTDOWN: Closing resources...")
    await close_mongo_connection()
    log.info("🛑 SHUTDOWN: Application terminated gracefully.")


app = FastAPI(
    title="Vyayamam AI Coach",
    version="1.0.0",
    lifespan=lifespan,
    default_response_class=Response(media_type="application/xml"),
)

app.include_router(whatsapp_router, prefix="/api")


@app.get("/", tags=["Root"], response_class=Response)
async def read_root():
    log.info("Received a GET request to the root endpoint.")
    return Response(
        content='{"message": "Welcome to the Vyayamam AI Coach API!"}',
        media_type="application/json",
    )
