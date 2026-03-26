class VertexError(Exception):
    """Base for all Vertex AI service errors."""


class VertexTimeoutError(VertexError):
    """Raised when the Vertex AI request exceeds its deadline."""


class VertexSafetyError(VertexError):
    """Raised when the prompt is rejected by the safety filter."""


class VertexAPIError(VertexError):
    """Raised for general Vertex AI API failures."""


class NoVideoGeneratedError(VertexError):
    """Raised when Vertex AI returns an empty video list."""
