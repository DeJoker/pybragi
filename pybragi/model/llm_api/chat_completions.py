import time
import traceback
import logging
import json
from concurrent.futures import ThreadPoolExecutor
from tornado import ioloop
from tornado.concurrent import run_on_executor
from tornado.iostream import StreamClosedError
from openai import OpenAI, NOT_GIVEN
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from pybragi.base.metrics import PrometheusMixIn

from pybragi.base.metrics import StreamMetrics

class ChatCompletions(PrometheusMixIn):
    executor: ThreadPoolExecutor

    # not emit this event
    def on_connection_close(self):
        logging.info("Connection close callback triggered")
        self.client_disconnected = True
        logging.info("Client disconnected, stopping stream")
        super().on_connection_close()

    def initialize(self, base_url: str, api_key: str, backend: str = "sglang_openai", max_running_count: int = 10):
        self.ioloop = ioloop.IOLoop.current()
        self.client_disconnected = False
        self.base_url = base_url
        self.api_key = api_key
        self.backend = backend
        self.max_running_count = max_running_count
    
    def fetch_openai_stream(self, **kwargs):
        client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            max_retries=1,
        )
        return client.chat.completions.create(
            model="",
            messages=kwargs.pop("messages", []),
            frequency_penalty=kwargs.pop("frequency_penalty", 0.0),
            max_tokens=kwargs.pop("max_tokens", 512),
            temperature=kwargs.pop("temperature", 0.8),
            top_p=kwargs.pop("top_p", 0.8),
            stream=kwargs.pop("stream", True),
            extra_body=kwargs
        )

    @run_on_executor
    def post(self):
        request = self.request.body
        request_json = json.loads(request)
        request_id = request_json.pop("request_id", "")
        timestamp2 = request_json.pop("timestamp2", round(time.time(), 3))
        messages = request_json.get("messages", [])
        stream = request_json.get("stream", True)

        if not stream:
            metrics = StreamMetrics(request_id, timestamp2, len(str(messages)))
            completion_result: ChatCompletion = self.fetch_openai_stream(**request_json)
            if completion_result.usage:
                prompt_tokens, completion_tokens = 0, 0
                if completion_result.usage.prompt_tokens:
                    prompt_tokens = completion_result.usage.prompt_tokens
                if completion_result.usage.completion_tokens:
                    completion_tokens = completion_result.usage.completion_tokens

                metrics.finish_infer(output_tokens=completion_tokens, prompt_tokens=prompt_tokens)
                logging.info(f"{metrics}")
            self.write(completion_result.model_dump_json())

            reply = ""
            if completion_result.choices[0].message.content:
                reply = completion_result.choices[0].message.content
            logging.info(f"{request_id}: {reply}")
            return


        # 设置SSE响应头
        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")

        chunk = None
        reply = ""
        try:
            metrics = StreamMetrics(request_id, timestamp2, len(str(messages)))
            completion_stream = self.fetch_openai_stream(**request_json)
            
            for chunk in completion_stream:
                chunk: ChatCompletionChunk
                if chunk.choices[0].delta.content:
                    metrics.output_token()
                    reply += chunk.choices[0].delta.content
                if self.client_disconnected:
                    logging.info("Stopping stream due to client disconnection")
                    completion_stream.close()
                    return
                
                self.write(f"data: {chunk.model_dump_json()}\n\n")
                self.ioloop.add_callback(self.flush)
            
        except StreamClosedError:
            completion_stream.close()
            logging.info("StreamClosedError detected, client disconnected")
            self.client_disconnected = True
            return
        except Exception as e:
            completion_stream.close()
            traceback.print_exc()
            logging.info(f"Error in post: {e}")
            return
        finally:
            if chunk and chunk.usage:
                prompt_tokens, completion_tokens = 0, 0
                if chunk.usage.prompt_tokens:
                    prompt_tokens = chunk.usage.prompt_tokens
                if chunk.usage.completion_tokens:
                    completion_tokens = chunk.usage.completion_tokens
                metrics.finish_infer(output_tokens=completion_tokens, prompt_tokens=prompt_tokens, backend=self.backend)
            else:
                metrics.finish_infer(0, 0)
                
            logging.info(f"{metrics}")
            logging.info(f"{request_id}: {reply}")

        self.write("data: [DONE]\n\n")
        return



def init_executor(max_workers: int):
    ChatCompletions.executor = ThreadPoolExecutor(max_workers=max_workers)
