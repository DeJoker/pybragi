import logging
import torch
from diffusers import FluxPipeline
from diffusers import DDPMScheduler, UNet2DModel

from pybragi.src.base import log
from pybragi.src.llm import model_utils

# md5sum /data2/hf_models/FLUX.1-dev/flux1-dev.safetensors # a6bd8c16dfc23db6aee2f63a2eba78c0
# md5sum /data2/rwy/wangxiang_ComfyUI/models/unet/flux1-dev.safetensors # a6bd8c16dfc23db6aee2f63a2eba78c0

flux_huggingface_dir = "/data2/hf_models/FLUX.1-dev"

flux = "/data2/rwy/wangxiang_ComfyUI/models/unet/flux1-dev.safetensors"
t5xxl = "/data2/rwy/wangxiang_ComfyUI/models/clip/t5xxl_fp16.safetensors"

flux_fp8 = "/data2/rwy/wangxiang_ComfyUI/models/unet/flux1-dev-fp8.safetensors"
t5xxl_fp8 = "/data2/rwy/wangxiang_ComfyUI/models/clip/t5xxl_fp8_e4m3fn.safetensors"

clip_l = "/data2/rwy/wangxiang_ComfyUI/models/clip/clip_l.safetensors"
vae_ae = "/data2/rwy/wangxiang_ComfyUI/models/vae/ae.safetensors"


def load_flux():
    
    pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-dev", torch_dtype=torch.bfloat16)
    pipe.enable_model_cpu_offload() #save some VRAM by offloading the model to CPU. Remove this if you have enough GPU power

    prompt = "A cat holding a sign that says hello world"
    image = pipe(
        prompt,
        height=1024,
        width=1024,
        guidance_scale=3.5,
        num_inference_steps=50,
        max_sequence_length=512,
        generator=torch.Generator("cpu").manual_seed(0)
    ).images[0]
    image.save("flux-dev.png")

def count_para():
    model_files = [flux_fp8, t5xxl_fp8, clip_l, vae_ae,]
    for file in model_files:
      tensors = model_utils.open_safetensor(file)
      logging.info(f"{file}")
      for k in tensors:
          print(f"{k} {tensors[k].shape} {tensors[k].nbytes} {tensors[k].numel()} ")
      sum(tensor.nbytes for tensor in tensors.values())
      logging.info(f"{file} dtype:{list(tensors.values())[0].dtype} nums:{sum(tensor.numel() for tensor in tensors.values())} nbytes:{sum(tensor.nbytes for tensor in tensors.values())}")

def load_flux_from_huggingface():
    from diffusers import AutoencoderKL, FlowMatchEulerDiscreteScheduler
    # from diffusers import schedulers
    from diffusers import FluxTransformer2DModel
    # from diffusers.models.transformers.transformer_flux import FluxTransformer2DModel
    from transformers import (
        AutoModelForTextEncoding,
        AutoTokenizer,

        CLIPTextModel,
        CLIPTokenizer,
        T5EncoderModel,
        T5TokenizerFast,
    )
    dtype = torch.float16

    scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(
        flux_huggingface_dir, subfolder="scheduler",
    )
    tokenizer = CLIPTokenizer.from_pretrained(
        flux_huggingface_dir, subfolder="tokenizer", torch_dtype=dtype
    )
    tokenizer_2 = T5TokenizerFast.from_pretrained(
        flux_huggingface_dir, subfolder="tokenizer_2", torch_dtype=dtype,
    )

    text_encoder = CLIPTextModel.from_pretrained(
        flux_huggingface_dir, subfolder="text_encoder", torch_dtype=dtype
    )
    text_encoder_2 = T5EncoderModel.from_pretrained(
        flux_huggingface_dir, subfolder="text_encoder_2", torch_dtype=dtype
    )
    vae = AutoencoderKL.from_pretrained(
        flux_huggingface_dir, subfolder="vae", torch_dtype=dtype,
    )

    transformer = FluxTransformer2DModel.from_pretrained(
        flux_huggingface_dir, subfolder="transformer", torch_dtype=dtype,
    )

    pipe = FluxPipeline(
            scheduler=scheduler,
            text_encoder=text_encoder,
            tokenizer=tokenizer,
            text_encoder_2=text_encoder_2,
            tokenizer_2=tokenizer_2,
            vae=vae,
            transformer=transformer,
        )
    
    return pipe



if __name__ == "__main__":
    load_flux_from_huggingface()
    # count_para()

