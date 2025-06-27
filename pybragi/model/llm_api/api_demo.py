import logging
import asyncio
from tornado import ioloop
from pybragi.model.llm_api import chat_completions, models
from pybragi.base.base_handler import make_tornado_web, run_tornado_app, register_exit_handler
from pybragi.base.shutdown import global_exit_event

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


    # 不要使用同步退出 否则会阻塞主线程
    # 不要使用 tornado_ioloop.add_callback_from_signal  要被  deprecated
    # add_signal_handler 需要在主线程调用  # RuntimeError: set_wakeup_fd only works in main thread of the main interpreter
    # tornado_ioloop = ioloop.IOLoop.current()
    # loop.add_signal_handler(signum, tornado_ioloop.stop)
    def exit_handler():
        global_exit_event().set() # 1. reject all incoming requests
        chat_completions.ChatCompletions.executor.shutdown() # 2. shutdown executor
        # 3. wait for all requests reply to client
        tornado_ioloop = ioloop.IOLoop.current()
        
        tornado_ioloop.add_callback_from_signal(tornado_ioloop.stop)
        # asyncio.get_event_loop().add_signal_handler(signal.SIGINT, tornado_ioloop.stop)

        logging.info("exit_handler done")


    async def exit_handler_async():
        logging.info("exit_handler_async start")
        loop = asyncio.get_event_loop()
        global_exit_event().set() # 1. reject all incoming requests

        # 2. shutdown executor
        await loop.run_in_executor(
            None,
            chat_completions.ChatCompletions.executor.shutdown
        )
        
        # 3. wait for all requests reply to client
        await asyncio.sleep(1)

        ioloop.IOLoop.current().stop()

    register_exit_handler(exit_handler_async)

    app = make_tornado_web("openai-transmit")
    app.add_handlers(".*", [
        (r"/v1/chat/completions", chat_completions.ChatCompletions, dict(base_url=args.base_url, api_key=args.api_key, backend=args.backend)),
        (r"/v1/models", models.Models, dict(openai_type=args.backend, get_models=get_models)),
    ])
    run_tornado_app(app, args.port)
    logging.info("run_tornado_app done")

