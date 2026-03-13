import json
import logging
import os

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# Defaulting to the Docker compose redis hostname
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")


@router.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logging.warning("✅ FASTAPI: Reflex client connected to websocket!")  # ADD THIS

    r = redis.from_url(REDIS_URL)
    pubsub = r.pubsub()

    try:
        await pubsub.psubscribe("job_updates_*")
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                data = json.loads(message["data"])
                logging.warning(f"🚀 FASTAPI: Received from Redis: {data}")  # ADD THIS
                await websocket.send_json(data)
                logging.warning("✅ FASTAPI: Pushed to Reflex!")  # ADD THIS

    except WebSocketDisconnect:
        logging.warning("❌ FASTAPI: Reflex client disconnected")
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        await pubsub.punsubscribe("job_updates_*")
        await r.close()