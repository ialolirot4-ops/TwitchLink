class Meta:
    APP_NAME = "TwitchLink"
    APP_VERSION = "3.5.4"
    HOMEPAGE_URL = "https://twitchlink.github.io"

    CONTACT = {
        "Email": "twitchlinkhelp@gmail.com"
    }

    @classmethod
    def getCopyrightInfo(cls) -> str:
        return "\u00a9 2021 DevHotteok."

    @classmethod
    def getProjectInfo(cls) -> str:
        lines = [
            f"{cls.APP_NAME} {cls.APP_VERSION}",
            f"Homepage  : {cls.HOMEPAGE_URL}",
            f"Copyright : {cls.getCopyrightInfo()}",
        ]
        return "\n".join(lines)