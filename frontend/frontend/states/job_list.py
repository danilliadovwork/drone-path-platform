import math
from typing import List, Dict, Any

import httpx
import reflex as rx
from frontend.annotations.notification import NotificationData
from frontend.constants.constants import PROCESS_VIDEO_HTTP_URL, JOBS_LIST_HTTP_URL, JOBS_DETAIL_HTTP_URL, \
    NOTIFICATIONS_WS_URI
from frontend.states.base import BaseState


class JobListState(BaseState):
    """Handles pagination and data fetching for the Jobs List page."""
    processed_jobs: List[Dict[str, Any]] = []
    total_jobs: int = 0
    page: int = 1
    limit: int = 100

    @rx.var
    def total_pages(self) -> int:
        """Calculates the total number of pages based on total jobs and limit."""
        return max(1, math.ceil(self.total_jobs / self.limit))

    async def fetch_jobs(self):
        """Fetches the jobs for the current page."""
        skip = (self.page - 1) * self.limit
        url = f"{JOBS_LIST_HTTP_URL}?skip={skip}&limit={self.limit}"

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
            return JobListState.fetch_jobs

    def prev_page(self):
        if self.page > 1:
            self.page -= 1
            return JobListState.fetch_jobs