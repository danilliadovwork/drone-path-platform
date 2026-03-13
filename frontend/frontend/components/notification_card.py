import reflex as rx

def notification_card(notification: dict):
    """A sleek, theme-aware card for job status."""
    return rx.card(
        rx.hstack(
            rx.text(f"Job #{notification['id']}", font_weight="bold"),
            rx.spacer(),
            # Using badges instead of raw text + emojis for a cleaner look
            rx.cond(
                notification["status"] == "completed",
                rx.badge("Completed", color_scheme="green", variant="soft"),
                rx.cond(
                    notification["status"] == "failed",
                    rx.badge("Failed", color_scheme="red", variant="soft"),
                    rx.badge("Processing...", color_scheme="orange", variant="soft")
                )
            ),
            width="100%",
            align_items="center",
        ),
        width="100%",
        variant="surface",  # Automatically adapts to dark/light theme
        margin_bottom="2",
        _hover={"cursor": "pointer", "opacity": "0.8"} # Shows users it's clickable
    )
