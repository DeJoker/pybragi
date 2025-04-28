from typing import Any, Callable, Dict
from pydantic import BaseModel, Field, field_validator

class Header(BaseModel):
    task_id: str = ""
    action: str = ""
    event: str = ""
    error_code: int = 0
    error_message: str = ""
    attributes: Dict[str, Any] = {}

# generated-audio & append-audio
class AudioGenerated(BaseModel):
    audio_size: int
    audio_duration: str
    last: bool = False


class TaskFinished(BaseModel):
    source_audio_url: str
    target_audio_url: str
    

class RunTask(BaseModel):
    task: str
    parameters: Dict[str, Any]


class Request(BaseModel):
    header: Header
    payload: Any = None
