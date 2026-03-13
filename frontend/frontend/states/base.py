import asyncio
import json
import logging
from typing import List

import reflex as rx
import websockets
from frontend.annotations.notification import NotificationData
from frontend.constants.constants import NOTIFICATIONS_WS_URI


# ==========================================
# 1. Global State (Shared across ALL pages)
# ==========================================
class BaseState(rx.State):
    """Holds global data and background tasks. Do NOT inherit this into other states."""
    notifications: List[NotificationData] = []

    @rx.event(background=True)
    async def connect_websocket(self):
        while True:
            try:
                logging.warning("🔄 REFLEX: Attempting to connect to FastAPI...")
                async with websockets.connect(NOTIFICATIONS_WS_URI) as ws:
                    logging.warning("✅ REFLEX: Connected to FastAPI!")
                    async for message in ws:
                        data = json.loads(message)
                        logging.warning(f"🎯 REFLEX: State successfully received data: {data}")
                        async with self:
                            new_notif = NotificationData(id=data["id"], status=data["status"])
                            self.notifications = [new_notif] + self.notifications[:9]

            except Exception as e:
                logging.error(f"REFLEX: WebSocket dropped: {e}. Retrying in 3s...")
                await asyncio.sleep(3)