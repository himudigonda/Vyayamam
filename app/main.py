# app/main.py

from fastapi import FastAPI, Response
from contextlib import asynccontextmanager
from app.db.database import connect_to_mongo, close_mongo_connection

# --- IMPORT THE ROUTER ---
from app.api.whatsapp import router as whatsapp_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(
    title="Vyayamam AI Coach",
    description="A hyper-personalized workout tracking and coaching system.",
    version="1.0.0",
    lifespan=lifespan,
    # This is important for returning XML content correctly
    default_response_class=Response(media_type="application/xml"),
)

# --- INCLUDE THE ROUTER ---
app.include_router(whatsapp_router, prefix="/api")


@app.get("/", tags=["Root"], response_class=Response)
async def read_root():
    return Response(
        content='{"message": "Welcome to the Vyayamam AI Coach API!"}',
        media_type="application/json",
    )
