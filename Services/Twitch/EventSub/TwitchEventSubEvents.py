class SubscriptionTypes:
    # Reemplaza video-playback-by-id → stream-up
    StreamOnline  = "stream.online"
    # Reemplaza video-playback-by-id → stream-down
    StreamOffline = "stream.offline"
    # Reemplaza broadcast-settings-update
    ChannelUpdate = "channel.update"

    @staticmethod
    def version(sub_type: str) -> str:
        return "1"
