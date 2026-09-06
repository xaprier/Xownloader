from threading import Lock


class Metrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._values = {
            "downloads_created_total": 0,
            "downloads_completed_total": 0,
            "downloads_failed_total": 0,
            "downloads_cancelled_total": 0,
        }

    def increment(self, name: str) -> None:
        with self._lock:
            self._values[name] += 1

    def prometheus(self) -> str:
        with self._lock:
            return "".join(
                f"# TYPE {name} counter\n{name} {value}\n"
                for name, value in self._values.items()
            )
