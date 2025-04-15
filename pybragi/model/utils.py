


import json
import logging
from typing import OrderedDict

from safetensors import safe_open
import torch


def read_config(configfile=""):
    with open(configfile, "r") as fp:
        return json.load(fp)

def calculate_parameters(config):
    hidden_size = config['hidden_size']
    intermediate_size = config['intermediate_size']
    max_position_embeddings = config['max_position_embeddings']
    vocab_size = config['vocab_size']
    num_hidden_layers = config['num_hidden_layers']
    num_attention_heads = config['num_attention_heads']

    
    embedding_params = vocab_size * hidden_size # Word Embeddings
    embedding_params += max_position_embeddings * hidden_size # Position Embeddings

    # 注意力层参数
    attention_head_size = hidden_size // num_attention_heads
    attention_params = (3 * hidden_size * attention_head_size) * num_attention_heads # QKV
    attention_params += 3 * hidden_size  # 添加偏置项

    # 前馈网络参数
    ff_params = (intermediate_size * hidden_size) * num_hidden_layers
    ff_params += (hidden_size * intermediate_size) * num_hidden_layers
    ff_params += 2 * intermediate_size * num_hidden_layers  # 添加偏置项

    # 层归一化参数
    layer_norm_params = 2 * hidden_size * num_hidden_layers

    # 最终线性层参数
    final_linear_params = vocab_size * hidden_size

    # 总参数量
    total_params = embedding_params + attention_params + ff_params + layer_norm_params + final_linear_params
    return total_params


def calculate_parameters2(config):
    vocab_size = config['vocab_size']
    hidden_size = config['hidden_size']
    max_position_embeddings = config['max_position_embeddings']
    num_hidden_layers = config['num_hidden_layers']
    intermediate_size = config['intermediate_size']

    # Embedding layers
    # no postion embedings  max_position_embeddings * hidden_size
    embedding_params = vocab_size * hidden_size

    # Transformer layers
    transformer_params = 0
    # Attention layer
    attention_params = (2 * hidden_size * hidden_size) # Q O
    attention_params = (2 * hidden_size * 512) # K V

    # attention_output_params = (hidden_size * hidden_size) # no bias
    
    # Feed-forward layer   mlp
    feed_forward_params = (hidden_size * intermediate_size * 3) # gate up down

    # LayerNorm parameters (2 per layer: pre-attention and post-attention)
    layernorm_params = 2 * hidden_size
    # layernorm_params = 0

    # Add layer params to total transformer params
    transformer_params = (attention_params \
                           + layernorm_params + feed_forward_params) * num_hidden_layers

    # Output layer lm_head
    output_params = hidden_size * vocab_size  # no bias

    # Total parameters
    total_params = embedding_params + transformer_params + output_params

    return total_params


def count_parameters(model, show_info=False):
    total = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_bytes = 0
    for name,p in model.named_parameters():
        if p.requires_grad and show_info:
            print(f"{name}, {p.device} {p.shape} {p.numel()}")
        total_bytes += p.nbytes
    
    logging.info(f"total_bytes:{total_bytes/1024**2:.2f}MB total:{total}")
    return total

def dicts_parameters(dicts: OrderedDict, show_info=False):
    # print("metadata:", dicts.get("_metadata", {}))

    total = sum(p.numel() if isinstance(p, torch.Tensor) else 0 for p in dicts.values())
    total_bytes = 0
    for name,p in dicts.items():
        if isinstance(p, torch.Tensor):
            if show_info:
                print(f"{name}, {p.device} {p.shape} {p.numel()}")
            total_bytes += p.nbytes
    
    logging.info(f"total_bytes:{total_bytes/1024**2:.2f}MB total:{total}")
    return total

def open_safetensor(model_file=""):
    tensors = {}
    with safe_open(model_file, framework="pt", device='cpu') as f:
        for k in f.keys():
            tensors[k] = f.get_tensor(k)
    return tensors
