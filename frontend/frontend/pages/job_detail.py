import reflex as rx

from frontend.components.notification_card import notification_card
from frontend.states.job_detail import JobDetailState


# 1. Add the route and on_load trigger so the state fetches fresh data
def job_detail():
    return rx.vstack(
        rx.heading(f"Job Details #{JobDetailState.selected_job['id']}"),
        rx.cond(
            JobDetailState.selected_job,
            rx.vstack(
                # Insert the card right at the top of the details section
                notification_card(JobDetailState.selected_job),

                rx.text(f"Predictor: {JobDetailState.selected_job['path_predictor_type']}", margin_top="2"),
                rx.text(f"Processed At: {JobDetailState.selected_job['processed_at']}"),

                rx.divider(margin_y="4"),

                # --- Map Rendering ---
                rx.cond(
                    JobDetailState.selected_job_map_html != "",
                    rx.el.iframe(
                        src=JobDetailState.selected_job_map_html, # 2. Change from srcdoc to src
                        width="100%",
                        height="500px",
                        style={
                            "border": "none",
                            "border-radius": "8px",
                            "background-color": "white"  # 3. Ensure tiles are visible against dark theme
                        }
                    ),
                    rx.text("No map trajectory available for this job.", color="gray")
                ),
                width="100%"
            ),
            rx.text("Loading...")
        ),
        rx.link("← Back to Jobs", href="/jobs", margin_top="4"),

        width="100%",
        max_width="800px",
        margin="auto",
        padding="6"
    )
