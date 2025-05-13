import time
import traceback
import logging
import json
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI, NOT_GIVEN
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from tornado import ioloop
from tornado.concurrent import run_on_executor
from tornado.iostream import StreamClosedError

from pybragi.base.metrics import PrometheusMixIn, StreamMetrics

from pybragi.server import dao_server_discovery
from pybragi.server.loadbalance import roundrobin, hash_balance

from .openai_transmit import Config, openai_type

# https://docs.vllm.ai/en/v0.7.1/serving/openai_compatible_server.html#completions-api
# {'raw_prompt': '...', 'request_id': '1745476824-d2416062-3a24-4d71-8c41-e20fe31cb117', 
# 'max_new_tokens': 1024, 'do_sample': True, 'top_p': 0.8, 'temperature': 0.8, 
# 'repetition_penalty': 1.05, 'top_k': 10, 'input_max_length': 8000, 
# 'timestamp': 1745476824, 'timestamp2': 1745476824.3741992, 'topic': 'aigc_qwen_queue', 'mid': 135201}

class ChatCompletions(PrometheusMixIn):
    executor = ThreadPoolExecutor(50)

    # not emit this event
    def on_connection_close(self):
        logging.info("Connection close callback triggered")
        self.client_disconnected = True
        logging.info("Client disconnected, stopping stream")
        super().on_connection_close()

    def initialize(self):
        self.ioloop = ioloop.IOLoop.current()
        self.client_disconnected = False
        self.request.connection.set_close_callback(self.on_connection_close)
    
    def fetch_openai_stream(self, host, **kwargs):
        client = OpenAI(
            base_url=f"{host}/v1",
            api_key="xxx",
            max_retries=1,
        )
        return client.chat.completions.create(
            model=kwargs.pop("model", ""),
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
        api_key = self.request.headers.get("Authorization", "")
        if api_key.startswith("Bearer "):
            api_key = api_key[7:]  # 移除"Bearer "前缀
        if not api_key:
            self.set_status(401)
            self.write({"error": {"message": "Missing API key"}})
            return
        if api_key != Config.ApiKey:
            self.set_status(401)
            self.write({"error": {"message": f"Invalid API key {api_key[:5]}...{api_key[-5:]}"}})
            return

        request = self.request.body
        request_json = json.loads(request)
        model = request_json.get("model", "")
        request_id = request_json.get("request_id", "")
        timestamp2 = request_json.get("timestamp2", round(time.time(), 3))
        messages = request_json.get("messages", [])
        stream = request_json.get("stream", True)

        servers = dao_server_discovery.get_server_online(model, openai_type)
        if not servers:
            self.set_status(503)
            self.write({"error": {"message": f"Not support model {model}"}})
            return
        
        host = roundrobin(servers)
        if not host:
            self.set_status(503)
            self.write({"error": {"message": "No healthy server found"}})
            return

        if not stream:
            metrics = StreamMetrics(request_id, timestamp2, len(str(messages)))
            completion_result: ChatCompletion = self.fetch_openai_stream(host, **request_json)
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

        reply = ""
        try:
            metrics = StreamMetrics(request_id, timestamp2, len(str(messages)))
            completion_stream = self.fetch_openai_stream(host, **request_json)
            
            for chunk in completion_stream:
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
                metrics.finish_infer(output_tokens=completion_tokens, prompt_tokens=prompt_tokens)
            else:
                metrics.finish_infer(0, 0, Config.Backend)
                
            logging.info(f"{metrics}")
            logging.info(f"{request_id}: {reply}")

        self.write("data: [DONE]\n\n")
        return


