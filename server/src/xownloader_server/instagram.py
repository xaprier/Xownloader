class InstagramAdapter:
    name = "instagram"

    def __init__(self, cookie: str, *, delay_seconds: float = 0.0) -> None:
        self._cookie = cookie
        self._delay_seconds = delay_seconds
