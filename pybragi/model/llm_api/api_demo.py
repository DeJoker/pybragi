from pybragi.model.llm_api import chat_completions, models
from pybragi.base.base_handler import make_tornado_web, run_tornado_app, register_exit_signal

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
    register_exit_signal()

    app = make_tornado_web("openai-transmit")
    app.add_handlers(".*", [
        (r"/v1/chat/completions", chat_completions.ChatCompletions, dict(base_url=args.base_url, api_key=args.api_key, backend=args.backend)),
        (r"/v1/models", models.Models, dict(openai_type=args.backend, get_models=get_models)),
    ])
    run_tornado_app(app, args.port)

