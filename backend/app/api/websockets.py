import json
import logging
import os

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Initialize the router for WebSocket connections
router = APIRouter()

# --- Configuration ---
# Uses the Redis connection string from environment variables.
# In a Docker environment, 'redis' resolves to the Redis container's internal IP.
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")


@router.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    """
    Manages long-lived WebSocket connections for real-time notifications.

    This endpoint subscribes to a Redis Pub/Sub channel. When the Celery worker
    finishes a task and publishes a message to Redis, this function catches it
    and immediately pushes it to the connected Reflex frontend.
    """
    # Accept the initial handshake from the client
    await websocket.accept()
    logging.warning("✅ FASTAPI: Reflex client connected to websocket!")

    # Establish an asynchronous connection to Redis
    r = redis.from_url(REDIS_URL)

    # Initialize the Pub/Sub (Publish/Subscribe) interface
    pubsub = r.pubsub()

    try:
        # --- Subscription ---
        # We use 'psubscribe' with a pattern ('*') so we can catch any
        # message sent to channels like 'job_updates_1', 'job_updates_2', etc.
        await pubsub.psubscribe("job_updates_*")

        # Listen for messages indefinitely in an async loop
        async for message in pubsub.listen():
            # Redis Pub/Sub yields several message types (subscribe, psubscribe, etc.)
            # We only care about 'pmessage', which contains the actual JSON data.
            if message["type"] == "pmessage":
                # Deserialize the Redis string back into a Python dictionary
                data = json.loads(message["data"])

                logging.warning(f"🚀 FASTAPI: Received from Redis: {data}")

                # --- Real-time Push ---
                # Push the data to the Reflex frontend. Reflex will receive this in
                # its 'connect_websocket' background task and update the State.
                await websocket.send_json(data)

                logging.warning("✅ FASTAPI: Pushed to Reflex!")

    except WebSocketDisconnect:
        # Standard cleanup when the user closes their browser or navigates away
        logging.warning("❌ FASTAPI: Reflex client disconnected")
    except Exception as e:
        # Catch unexpected network or JSON decoding errors
        logging.error(f"WebSocket error: {e}")
    finally:
        # --- Cleanup ---
        # Ensure we unsubscribe and close connections to prevent memory leaks in Redis
        await pubsub.punsubscribe("job_updates_*")
        await r.close()