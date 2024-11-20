
import logging
import os, pytest
import torch
from pybragi.src.base import log
from pybragi.src.llm import model_utils
from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig
from safetensors import safe_open
from vllm.utils import CudaMemoryProfiler


models_to_test = [
    "/aigc-nas02/hf_models/Qwen2-72B-Instruct/config.json",
    "/aigc-nas02/hf_models/Qwen2-7B/config.json",
]

model_72B = "/aigc-nas02/hf_models/Qwen2-72B-Instruct" # 7615616512
# transformers Loading model weights took 67.3281 GB
# Loading model weights took 67.8001 GB

model_7B = "/aigc-nas02/hf_models/Qwen2-7B" # 7615616512
# Loading model weights took 14.2716 GB
# transformers Loading model weights took 15.9772 GB

os.environ["OMP_NUM_THREADS"] = "4"
# os.environ["CUDA_VISIBLE_DEVICES"] = "4,7"
os.environ["CUDA_VISIBLE_DEVICES"] = "4"

@pytest.mark.parametrize("config_dir", models_to_test)
def test_model_parameters(config_dir):
    config = model_utils.read_config(config_dir)
    x = model_utils.calculate_parameters(config)
    print(x)

@pytest.mark.parametrize("config_dir", models_to_test)
def test_model_parameters2(config_dir):
    config = model_utils.read_config(config_dir)
    x = model_utils.calculate_parameters2(config)
    print(x)


def test_real_parameters(model_name=model_7B):
    from vllm.utils import CudaMemoryProfiler
    # 有一些torch parameter 是meta类型
    # with CudaMemoryProfiler() as m:
    #     model = AutoModelForCausalLM.from_pretrained(
    #         model_name,
    #         torch_dtype="auto",
    #         # device="cuda",
    #     )
    #     tokenizer = AutoTokenizer.from_pretrained(model_name)
    #     logging.info(f"{type(model)}") # Qwen2ForCausalLM

    with CudaMemoryProfiler() as m:
        from accelerate import infer_auto_device_map, init_empty_weights, load_checkpoint_and_dispatch

        config = AutoConfig.from_pretrained(model_name)
        with init_empty_weights():
            model = AutoModelForCausalLM.from_config(config, torch_dtype=torch.float16)

        max_memory = {0: "74GiB", "cpu": "100GiB"}
        device_map = infer_auto_device_map(model, max_memory=max_memory,)

        model = load_checkpoint_and_dispatch(model, model_name, device_map=device_map,)
        logging.info(f"{type(model)}") # Qwen2ForCausalLM


    xx = model_utils.count_parameters(model, show_info=True)
    logging.info(xx)
    logging.info("transformers Loading model weights took %.4f GB", m.consumed_memory / float(2**30))


def test_parameters333():
    x1 = 152064 * 3584
    x2 = 3584 * 3584 *2 + 3584 * 512 *2 + 3584*18944*3
    x2 += 512*2 + 3584 # bias
    x2 += 3584 # layernorm
    x2 *= 28

    x3 = x1

    print(x1+x2+x3 + 131072)


def safetensor_check(model_dir=""):
    tensors = {}
    with safe_open(model_dir, framework="pt", device='cpu') as f:
        for k in f.keys():
            tensors[k] = f.get_tensor(k)

            zero_mask = tensors[k] <= 1e-7

            torch.sum(tensors[k] <= 1e-7) == tensors[k].numel()

            logging.info(f"{k} {tensors[k].nbytes} {tensors[k].numel()} "
                        f"{zero_mask.sum()} {torch.nonzero(tensors[k]).size(0)}"
                    )

    
    logging.info(f"{tensors}")


def vllm_load_model():
    test_real_parameters(model_72B)

    from vllm import EngineArgs, LLMEngine, RequestOutput, SamplingParams
    engine_args = EngineArgs(model=model_72B, dtype=torch.float16,
                             use_v2_block_manager=False,
                             gpu_memory_utilization=0.92, trust_remote_code=True,
                             enforce_eager=True,
                             enable_prefix_caching=True, enable_chunked_prefill=True,
                            #  worker_use_ray=True,
                            #  tensor_parallel_size=2,
                             max_model_len=2048
                            )
    engine = LLMEngine.from_engine_args(engine_args)
    return

if __name__ == "__main__":
    # 2491416720 Sep 14 10:15
    # nbytes 2491416576
    # safetensor_check("/aigc-nas02/zpfcode/train_model/qwen-sft-0905/model-00001-of-00082.safetensors")

    # test_real_parameters()

    vllm_load_model()


