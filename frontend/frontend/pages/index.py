import reflex as rx
from frontend.states.state import State
from frontend.components.live_notifications_overlay import live_notifications_overlay


@rx.page(on_load=State.connect_websocket)
def index():
    return rx.box(
        rx.vstack(
            rx.heading("Drone Path Predictor", margin_bottom="6", align="center"),

            # --- Form Section ---
            rx.input(placeholder="Google Drive Link", on_change=State.set_gdrive_link, width="100%"),

            rx.vstack(
                rx.input(placeholder="Start Latitude", default_value="50.13", on_change=State.set_start_lat,
                         width="100%"),
                rx.input(placeholder="Start Longitude", default_value="36.27", on_change=State.set_start_lon,
                         width="100%"),
                rx.text("If geo coordinates exist inside video, no need to set it.", size="1", color="gray"),
                spacing="2",
                width="100%"
            ),

            rx.select(
                ["OPTICAL_FLOW", "DEEP_LEARNING"],
                placeholder="Select Path Predictor",
                default_value="DEEP_LEARNING",
                value=State.path_predictor_type,
                on_change=State.set_path_predictor_type,
                width="100%"
            ),

            rx.button("Submit Video", on_click=State.submit, width="100%", size="3"),

            rx.divider(margin_y="6"),

            rx.link(
                rx.button("View All Processed Jobs", variant="soft", width="100%"),
                href="/jobs",
                width="100%"
            ),

            width="100%",
            max_width="500px",  # Slightly tighter for a better form aesthetic
            padding="8",
            border_radius="lg",
            box_shadow="0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",  # Subtle depth
            background_color=rx.color("gray", 2),  # Theme-aware background
        ),

        # --- The New Floating Overlay ---
        live_notifications_overlay(),

        # --- Screen Centering Properties ---
        width="100%",
        min_height="100vh",
        display="flex",
        align_items="center",
        justify_content="center",
    )
