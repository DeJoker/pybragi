from typing import Any, Callable, Dict
from pydantic import BaseModel, Field, field_validator, model_validator


# 客户端发送 action   服务器接收 action
run_task_action = "run-task"
append_audio_action = "append-audio"
finish_task_action = "finish-task"
valid_actions = [run_task_action, append_audio_action, finish_task_action]

# 服务端发送 event  客户端接收 event
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

    @model_validator(mode='after')
    def check_action_or_event(self) -> 'Header':
        action_provided = bool(self.action)
        event_provided = bool(self.event)

        if not action_provided and not event_provided:
            raise ValueError("must provide either action or event")

        if action_provided and self.action not in valid_actions:
            raise ValueError(f"invalid action '{self.action}'. must be one of {valid_actions}")

        if event_provided and self.event not in valid_events:
            raise ValueError(f"invalid event '{self.event}'. must be one of {valid_events}")

        return self


# generated-audio & append-audio
class AudioInfo(BaseModel):
    audio_size: int
    audio_duration: str
    last: bool = False


class TaskFinished(BaseModel):
    source_audio_url: str = ""
    seed_audio_url: str = ""
    rvc_audio_url: str = ""
    target_audio_url: str = ""

class RunTask(BaseModel):
    task: str
    parameters: Dict[str, Any]


class Request(BaseModel):
    header: Header
    payload: Any = None



code_shutting_down = 1000
code_force_close = 1001
code_exception = 1002
code_invalid_parameters = 1003
code_auth_failed = 1004
