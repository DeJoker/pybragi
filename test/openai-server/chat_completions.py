import traceback
import logging
import json
from concurrent.futures import ThreadPoolExecutor
from tornado.concurrent import run_on_executor

from tornado.iostream import StreamClosedError
from pybragi.base.metrics import PrometheusMixIn

from pybragi.base.metrics import StreamMetrics

from .openai_transmit import Config
        
class ChatCompletions(PrometheusMixIn):
    executor = ThreadPoolExecutor(Config.MaxRunningCount+2)

    # not emit this event
    def on_connection_close(self):
        logging.info("Connection close callback triggered")
        self.client_disconnected = True
        logging.info("Client disconnected, stopping stream")
        super().on_connection_close()

    def initialize(self):
        self.client_disconnected = False
        self.request.connection.set_close_callback(self.on_connection_close)
    
    @run_on_executor
    def fetch_openai_stream(self, **kwargs):
        from openai import OpenAI
        client = OpenAI(
            base_url=f"http://localhost:{Config.OpenAIPort}/v1",
            api_key="xxx",
            max_retries=1,
            timeout=2,
        )
        return client.chat.completions.create(
            model="",
            messages=kwargs.pop("messages", []),
            frequency_penalty=kwargs.pop("frequency_penalty", None),
            max_tokens=kwargs.pop("max_tokens", 512),
            temperature=kwargs.pop("temperature", 0.8),
            top_p=kwargs.pop("top_p", 0.8),
            stream=True,
            extra_body=kwargs
        )

    async def post(self):
        request = self.request.body
        request_json = json.loads(request)
        request_id = request_json.pop("request_id", "")
        timestamp2 = request_json.pop("timestamp2", 0)

        # 设置SSE响应头
        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")

        reply = ""
        try:
            metrics = StreamMetrics(request_id, timestamp2, 3)
            completion_stream = await self.fetch_openai_stream(**request_json)
            
            for chunk in completion_stream:
                if chunk.choices[0].delta.content:
                    metrics.output_token()
                    reply += chunk.choices[0].delta.content
                if self.client_disconnected:
                    logging.info("Stopping stream due to client disconnection")
                    completion_stream.close()
                    return
                
                self.write(f"data: {chunk.model_dump_json()}\n\n")
                await self.flush()
            
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
            metrics.finish_infer(0, Config.Backend)
            logging.info(f"{metrics}")
            logging.info(f"{request_id}: {reply}")

        self.write("data: [DONE]\n\n")
        return


