class PolicyViolation(Exception):
    """Raised when a request exceeds a configured server policy."""


class RateLimitExceeded(Exception):
    """Raised when a client exceeds its request rate."""


class QueueFull(Exception):
    """Raised when the server queue cannot accept another job."""


class InsufficientStorage(Exception):
    """Raised when the configured free-disk reserve is unavailable."""


class JobNotFound(Exception):
    """Raised when a requested job does not exist."""