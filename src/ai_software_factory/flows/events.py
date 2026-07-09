from pydantic import BaseModel, ConfigDict


class WorkflowEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str
    stage: str
    message: str
