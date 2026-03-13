from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.api.websockets import router as ws_router
from app.core.database import engine, Base

app = FastAPI()

# 1. Define allowed origins (your Reflex frontend)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://0.0.0.0:3000",
]

# 2. Add CORS Middleware to the application
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# 3. Include your standard and websocket routers
app.include_router(api_router, prefix="/api")
app.include_router(ws_router)

@app.get("/")
def read_root():
    return {"message": "Drone Path Predictor API"}
