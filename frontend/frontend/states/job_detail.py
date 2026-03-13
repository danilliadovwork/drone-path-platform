import base64
import json
import logging
from typing import Dict, Any

import httpx

from frontend.annotations.notification import NotificationData
from frontend.constants.constants import PROCESS_VIDEO_HTTP_URL, JOBS_LIST_HTTP_URL, JOBS_DETAIL_HTTP_URL, \
    NOTIFICATIONS_WS_URI
from frontend.states.base import BaseState


class JobDetailState(BaseState):
    """Handles fetching individual job data and rendering the Folium map."""
    path_id: int = 0
    status: str = ""
    trajectory: str = ""
    selected_job: Dict[str, Any] = {}
    selected_job_map_html: str = ""

    async def fetch_job_detail(self):
        if not self.job_id:
            return

        url = JOBS_DETAIL_HTTP_URL.format(job_id=self.job_id)

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
        import folium

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

            # Get the raw HTML string
            html_string = m.get_root().render()

            # Encode as Base64 to bypass React's strict iframe string parsing
            b64_html = base64.b64encode(html_string.encode("utf-8")).decode("utf-8")

            # Save as a Data URI
            self.selected_job_map_html = f"data:text/html;base64,{b64_html}"
        except Exception as e:
            logging.error(f"Folium map error: {e}")
            self.selected_job_map_html = ""