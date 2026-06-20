"""Application-specific exceptions."""


class ResearchAgentError(Exception):
    """Base exception for errors that can be shown directly to a CLI user."""


class ConfigurationError(ResearchAgentError):
    """Raised when required runtime configuration is invalid or missing."""


class DependencyError(ResearchAgentError):
    """Raised when optional runtime dependencies have not been installed."""


class WorkflowError(ResearchAgentError):
    """Raised when the research workflow cannot complete."""
