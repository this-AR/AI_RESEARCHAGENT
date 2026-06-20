"""Validated input models that do not require an external package."""

from dataclasses import asdict, dataclass

from .errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class ResearchTarget:
    company_name: str
    industry: str
    key_decision_maker: str
    position: str
    recent_milestone: str

    def __post_init__(self) -> None:
        for field_name, value in asdict(self).items():
            if not value.strip():
                readable = field_name.replace("_", " ")
                raise ConfigurationError(f"Target {readable} cannot be empty.")

    def as_inputs(self) -> dict[str, str]:
        return asdict(self)
