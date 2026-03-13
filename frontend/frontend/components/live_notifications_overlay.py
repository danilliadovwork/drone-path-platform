import reflex as rx

from frontend.states.base import BaseState
from frontend.annotations.notification import NotificationData


def clickable_live_card(notification: NotificationData):
    return rx.link(
        rx.card(
            rx.hstack(
                rx.text(f"Job #{notification.id}", weight="bold"),
                rx.badge(notification.status, color_scheme="orange"),
                justify="between",
                width="100%"
            ),
            width="100%",
            padding="3"
        ),
        href=f"/jobs/{notification.id}",
        text_decoration="none",
        width="100%"
    )

def live_notifications_overlay():
    return rx.box(
        rx.cond(
            BaseState.notifications,
            rx.vstack(
                rx.text("Live Job Updates", size="2", color="gray", weight="bold"),
                rx.foreach(BaseState.notifications, clickable_live_card),
                spacing="2"
            ),
            rx.fragment()
        ),
        position="fixed",
        bottom="20px",
        right="20px",
        width="320px",
        z_index="9999",
    )