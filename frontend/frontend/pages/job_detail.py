import reflex as rx
from frontend.states.state import State
from frontend.components.notification_card import notification_card


# 1. Add the route and on_load trigger so the state fetches fresh data
@rx.page(route="/jobs/[job_id]", on_load=State.fetch_job_detail)
def job_detail():
    return rx.vstack(
        rx.heading(f"Job Details #{State.selected_job['id']}"),
        rx.cond(
            State.selected_job,
            rx.vstack(
                # Insert the card right at the top of the details section
                notification_card(State.selected_job),

                rx.text(f"Predictor: {State.selected_job['path_predictor_type']}", margin_top="2"),
                rx.text(f"Processed At: {State.selected_job['processed_at']}"),

                rx.divider(margin_y="4"),

                # --- Map Rendering ---
                rx.cond(
                    State.selected_job_map_html != "",
                    rx.el.iframe(
                        src=State.selected_job_map_html, # 2. Change from srcdoc to src
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
