from ai_software_factory.models import CrewDefinition


class CrewRegistry:
    def __init__(self) -> None:
        self._crews: dict[str, CrewDefinition] = {}

    def register(self, definition: CrewDefinition) -> None:
        if definition.id in self._crews:
            raise ValueError(f"Duplicate crew: {definition.id}")
        self._crews[definition.id] = definition

    def get(self, crew_id: str) -> CrewDefinition:
        return self._crews[crew_id]

    def list(self) -> list[CrewDefinition]:
        return list(self._crews.values())
