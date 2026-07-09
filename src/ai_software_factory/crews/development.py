# mypy: ignore-errors
from ai_software_factory.crews.base import BaseCrew


class DevelopmentCrew(BaseCrew):
    crew_id = "development"
