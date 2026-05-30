class Config:
    HOST                  = "wss://eventsub.wss.twitch.tv/ws"
    HELIX_SUBSCRIPTIONS   = "https://api.twitch.tv/helix/eventsub/subscriptions"
    RECONNECT_INTERVAL    = 3_000   # ms entre intentos de reconexión
    KEEPALIVE_MARGIN_MS   = 5_000   # ms extra sobre keepalive_timeout_seconds del servidor
