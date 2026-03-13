import reflex as rx
from frontend.states.index import IndexState
from frontend.states.job_list import JobListState
from frontend.states.job_detail import JobDetailState
from frontend.pages.index import index
from frontend.pages.jobs_list import jobs_list
from frontend.pages.job_detail import job_detail

app = rx.App()
app.add_page(
    index,
    route="/",
    on_load=IndexState.connect_websocket
)
app.add_page(
    jobs_list,
    route="/jobs",
    on_load=[
        JobListState.fetch_jobs,
        JobListState.connect_websocket
    ]
)
app.add_page(
    job_detail,
    route="/jobs/[job_id]",
    on_load=[
        JobDetailState.fetch_job_detail,
        JobDetailState.connect_websocket
    ]
)