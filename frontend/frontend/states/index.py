import httpx
import reflex as rx
from frontend.annotations.notification import NotificationData
from frontend.states.base import BaseState
from frontend.constants.constants import PROCESS_VIDEO_HTTP_URL, JOBS_LIST_HTTP_URL, JOBS_DETAIL_HTTP_URL, \
    NOTIFICATIONS_WS_URI


class IndexState(BaseState):
    """Handles form inputs and submissions for the main processing page."""
    gdrive_link: str = ""
    start_lat: str = "50.13"
    start_lon: str = "36.27"
    path_predictor_type: str = "OPTICAL_FLOW"
    is_submitting: bool = False

    def set_path_predictor_type(self, value: str):
        self.path_predictor_type = value

    async def submit(self):
        # Turn on the loading spinner and immediately update the UI
        self.is_submitting = True
        yield

        # Form Validation
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

        payload = {
            "gdrive_link": self.gdrive_link,
            "start_lat": lat,
            "start_lon": lon,
            "path_predictor_type": self.path_predictor_type
        }

        # Make the API Call
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(PROCESS_VIDEO_HTTP_URL, json=payload)
        except httpx.HTTPError as e:
            self.is_submitting = False
            yield rx.toast.error(f"Backend connection error: {e}")
            return

        # Turn off the loading spinner
        self.is_submitting = False

        # Handle Backend Response
        if response.status_code not in (httpx.codes.OK, httpx.codes.CREATED):
            yield rx.toast.error(f"Error from server: {response.text}")
            return

        yield rx.toast.success("Video submitted! Tracking progress in background.")
        return