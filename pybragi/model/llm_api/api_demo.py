import asyncio
from tornado import ioloop
import logging
import time
from pybragi.model.llm_api import chat_completions, models
from pybragi.base.base_handler import make_tornado_web, run_tornado_app, register_exit_signal
from pybragi.base.species_queue import global_exit_event

def get_models():
    return [
        {"id": "get_model_demo", "object": "model"},
    ]

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--backend", type=str, default="sglang_openai")
    parser.add_argument("--base_url", type=str)
    parser.add_argument("--api_key", type=str)
    args = parser.parse_args()

    chat_completions.init_executor(10)

    loop = asyncio.get_event_loop()

    # add_signal_handler 需要在主线程调用  # RuntimeError: set_wakeup_fd only works in main thread of the main interpreter
    # tornado_ioloop = ioloop.IOLoop.current()
    # loop.add_signal_handler(signum, tornado_ioloop.stop)
    def exit_handler():
        logging.info("exit_handler start")
        global_exit_event().set() # 1. reject all incoming requests
        chat_completions.ChatCompletions.executor.shutdown() # 2. shutdown executor
        # 3. wait for all requests reply to client
        loop.stop()

        logging.info("exit_handler done")

    register_exit_signal(exit_handler)

    app = make_tornado_web("openai-transmit")
    app.add_handlers(".*", [
        (r"/v1/chat/completions", chat_completions.ChatCompletions, dict(base_url=args.base_url, api_key=args.api_key, backend=args.backend)),
        (r"/v1/models", models.Models, dict(openai_type=args.backend, get_models=get_models)),
    ])
    run_tornado_app(app, args.port)

