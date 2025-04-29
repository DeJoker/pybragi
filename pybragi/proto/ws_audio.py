from typing import Any, Callable, Dict
from pydantic import BaseModel, Field, field_validator


run_task_action = "run-task"
append_audio_action = "append-audio"
finish_task_action = "finish-task"
valid_actions = [run_task_action, append_audio_action, finish_task_action]


task_started_event = "task-started"
result_generated_event = "result-generated"
audio_received_event = "audio-received"
task_finished_event = "task-finished"
task_failed_event = "task-failed"
valid_events = [task_started_event, result_generated_event, audio_received_event, task_finished_event, task_failed_event]


class Header(BaseModel):
    task_id: str = ""
    action: str = ""
    event: str = ""
    error_code: int = 0
    error_message: str = ""
    attributes: Dict[str, Any] = {}

    @field_validator('action', mode='after')
    @classmethod
    def validate_action(cls, v):
        if v not in valid_actions:
            raise ValueError(f"action must be one of {valid_actions}")
        return v
    
    @field_validator('event', mode='after')
    @classmethod
    def validate_event(cls, v):
        if v not in valid_events:
            raise ValueError(f"event must be one of {valid_events}")
        return v

# generated-audio & append-audio
class AudioInfo(BaseModel):
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



