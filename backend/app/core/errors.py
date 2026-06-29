class ExternalServiceError(RuntimeError):
    """Represent a recoverable external integration failure.

    Parameters:
        message: Human-readable failure reason.

    Returns:
        Exception instance.

    Edge cases:
        Used for fallback paths, not for programming errors.
    """
