import reflex as rx

config = rx.Config(
    app_name="frontend",
    api_url="http://localhost:8001",
    backend_port=8001,
    state_auto_setters=True, # <-- Add this line
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
    cors_allowed_origins=[
        "http://localhost:3000",
        "http://0.0.0.0:3000",
    ],
)