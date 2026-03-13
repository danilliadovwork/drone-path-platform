import asyncio
import logging
import math

import reflex as rx
import httpx
import json
import websockets
from typing import List, Dict, Any

from frontend.annotations.notification import NotificationData


class State(rx.State):
    gdrive_link: str = ""
    start_lat: str = "50.13"
    start_lon: str = "36.27"
    path_predictor_type: str = "OPTICAL_FLOW"
    path_id: int = 0
    status: str = ""
    trajectory: str = ""
    processed_jobs: List[Dict[str, Any]] = []
    total_jobs: int = 0
    page: int = 1
    limit: int = 100
    selected_job: Dict[str, Any] = {}
    notifications: List[NotificationData] = []
    selected_job_map_html: str = ""
    is_submitting: bool = False

    def set_path_predictor_type(self, value: str):
        self.path_predictor_type = value

    async def submit(self):
        # 1. Turn on the loading spinner and immediately update the UI
        self.is_submitting = True
        yield
        # 2. Form Validation
        if not self.gdrive_link:
            self.is_submitting = False
            yield rx.toast.error("Please enter a Google Drive link.")
            return
        try:
            lat = float(self.start_lat)
            lon = float(self.start_lon)
        except ValueError:
            self.is_submitting = False
            yield rx.toast.error("Coordinates must be valid numbers.")
            return
        url = "http://backend:7000/api/process"
        payload = {
            "gdrive_link": self.gdrive_link,
            "start_lat": lat,
            "start_lon": lon,
            "path_predictor_type": self.path_predictor_type
        }
        # 3. Make the API Call
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
        except httpx.HTTPError as e:
            self.is_submitting = False
            yield rx.toast.error(f"Backend connection error: {e}")
            return

        # 4. Turn off the loading spinner
        self.is_submitting = False

        # 5. Handle Backend Response
        if response.status_code not in (httpx.codes.OK, httpx.codes.CREATED):
            yield rx.toast.error(f"Error from server: {response.text}")
            return

        # If successful, pop a quick success message.
        # The WebSocket floating overlay will take over tracking the actual progress.
        yield rx.toast.success("Video submitted! Tracking progress in background.")
        return

    @rx.event(background=True)
    async def connect_websocket(self):
        uri = "ws://backend:7000/ws/notifications"

        while True:
            try:
                logging.warning("🔄 REFLEX: Attempting to connect to FastAPI...")  # ADD THIS
                async with websockets.connect(uri) as ws:
                    logging.warning("✅ REFLEX: Connected to FastAPI!")  # ADD THIS
                    async for message in ws:
                        data = json.loads(message)
                        logging.warning(f"🎯 REFLEX: State successfully received data: {data}")  # ADD THIS
                        async with self:
                            # 3. Instantiate the class instead of appending the raw dict
                            new_notif = NotificationData(id=data["id"], status=data["status"])
                            self.notifications = [new_notif] + self.notifications[:9]

            except Exception as e:
                logging.error(f"REFLEX: WebSocket dropped: {e}. Retrying in 3s...")
                await asyncio.sleep(3)

    async def fetch_trajectory(self):
        url = f"http://backend:7000/api/paths/{self.path_id}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
        except httpx.HTTPError as e:
            self.status = f"Error: {str(e)}"
            return

        if response.status_code == httpx.codes.OK:
            data = response.json()
            self.trajectory = data.get("trajectory", "")
        else:
            self.status = f"Error: {response.text}"

    async def fetch_job_detail(self):
        # 2. Update this logic to use the auto-populated state variable
        if not self.job_id:
            return

        url = f"http://backend:7000/api/jobs/{self.job_id}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
        except httpx.HTTPError as e:
            logging.error(f"Error fetching job details: {e}")
            return

        if response.status_code == httpx.codes.OK:
            self.selected_job = response.json()

            # Extract GeoJSON and generate the map
            flight_path = self.selected_job.get("flight_path", {})
            trajectory_str = flight_path.get("trajectory") if flight_path else None

            if trajectory_str:
                self.generate_map(trajectory_str)
            else:
                self.selected_job_map_html = ""

    def generate_map(self, geojson_str: str):
        """Converts raw GeoJSON into a Base64-encoded Folium HTML map."""
        import base64
        import folium
        import json

        try:
            geojson_data = json.loads(geojson_str)

            # GeoJSON coordinates are [Longitude, Latitude]
            coords = geojson_data.get("coordinates", [])
            if coords:
                start_lon, start_lat = coords[0]
                m = folium.Map(location=[start_lat, start_lon], zoom_start=18)
            else:
                m = folium.Map(location=[0, 0], zoom_start=2)

            # Add the GeoJSON path to the map
            folium.GeoJson(geojson_data, name="Drone Trajectory").add_to(m)

            # 1. Get the raw HTML string
            html_string = m.get_root().render()

            # 2. Encode as Base64 to bypass React's strict iframe string parsing
            b64_html = base64.b64encode(html_string.encode("utf-8")).decode("utf-8")

            # 3. Save as a Data URI
            self.selected_job_map_html = f"data:text/html;base64,{b64_html}"
        except Exception as e:
            logging.error(f"Folium map error: {e}")
            self.selected_job_map_html = ""

    @rx.var
    def total_pages(self) -> int:
        """Calculates the total number of pages based on total jobs and limit."""
        return max(1, math.ceil(self.total_jobs / self.limit))

    async def fetch_jobs(self):
        """Fetches the jobs for the current page."""
        skip = (self.page - 1) * self.limit
        url = f"http://backend:7000/api/jobs?skip={skip}&limit={self.limit}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)

            if response.status_code == httpx.codes.OK:
                data = response.json()
                self.total_jobs = data.get("total", 0)
                self.processed_jobs = data.get("items", [])
        except httpx.HTTPError as e:
            print(f"Error fetching jobs: {e}")

    def next_page(self):
        if self.page < self.total_pages:
            self.page += 1
            return State.fetch_jobs

    def prev_page(self):
        if self.page > 1:
            self.page -= 1
            return State.fetch_jobs
