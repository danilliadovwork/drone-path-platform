import reflex as rx
from frontend.states.state import State
from frontend.pages.index import index
from frontend.pages.jobs_list import jobs_list
from frontend.pages.job_detail import job_detail

app = rx.App()
app.add_page(index, route="/", on_load=State.connect_websocket)

# Start the listener on the jobs pages too!
app.add_page(jobs_list, route="/jobs", on_load=[State.fetch_jobs, State.connect_websocket])
app.add_page(job_detail, route="/jobs/[job_id]", on_load=[State.fetch_job_detail, State.connect_websocket])