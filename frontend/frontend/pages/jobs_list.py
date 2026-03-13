import reflex as rx

from frontend.components.live_notifications_overlay import live_notifications_overlay
from frontend.components.notification_card import notification_card
from frontend.states.job_list import JobListState


def clickable_job_card(job: dict):
    """Wraps the card in a structural link to make the whole block clickable."""
    return rx.link(
        notification_card(job),
        href=f"/jobs/{job['id']}",
        text_decoration="none",  # Prevents underline on hover
        width="100%"
    )


def jobs_list():
    return rx.box(
        rx.vstack(
            rx.heading("Processed Jobs", margin_bottom="4"),

            # --- Jobs List ---
            rx.cond(
                JobListState.processed_jobs,
                rx.vstack(
                    rx.foreach(
                        JobListState.processed_jobs,
                        clickable_job_card
                    ),
                    width="100%"
                ),
                rx.text("No jobs found.", color="gray")
            ),

            # --- Pagination Controls ---
            rx.hstack(
                rx.button(
                    "← Previous",
                    on_click=JobListState.prev_page,
                    disabled=JobListState.page <= 1,
                    variant="soft"
                ),
                rx.text(f"Page {JobListState.page} of {JobListState.total_pages}", align="center"),
                rx.button(
                    "Next →",
                    on_click=JobListState.next_page,
                    disabled=JobListState.page >= JobListState.total_pages,
                    variant="soft"
                ),
                width="100%",
                justify="between",
                align_items="center",
                margin_top="6"
            ),

            rx.divider(margin_y="6"),

            rx.hstack(
                rx.button("Refresh", on_click=JobListState.fetch_jobs, variant="outline"),
                rx.link(rx.button("Back to Home", variant="ghost"), href="/"),
            ),

            width="100%",
            max_width="600px",
            margin="auto",
            padding="6",
            padding_top="12"
        )
    )