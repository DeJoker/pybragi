


import json
import logging
from typing import OrderedDict



import shutil
from subprocess import Popen, PIPE
import os
import platform

class GPU:
    def __init__(self, ID, uuid, load, memoryTotal, memoryUsed, memoryFree, driver, gpu_name, serial, display_mode, display_active, temp_gpu):
        self.id = ID
        self.uuid = uuid
        self.load = load
        self.memoryUtil = float(memoryUsed)/float(memoryTotal)
        self.memoryTotal = memoryTotal
        self.memoryUsed = memoryUsed
        self.memoryFree = memoryFree
        self.driver = driver
        self.name = gpu_name
        self.serial = serial
        self.display_mode = display_mode
        self.display_active = display_active
        self.temperature = temp_gpu

def safeFloatCast(strNumber):
    try:
        number = float(strNumber)
    except ValueError:
        number = float('nan')
    return number

def getGPUs():
    creationflags = 0
    if platform.system() == "Windows":
        from subprocess import CREATE_NO_WINDOW
        creationflags = CREATE_NO_WINDOW
        
        # If the platform is Windows and nvidia-smi 
        # could not be found from the environment path, 
        # try to find it from system drive with default installation path
        nvidia_smi = shutil.which('nvidia-smi')
        if nvidia_smi is None:
            nvidia_smi = "%s\\Program Files\\NVIDIA Corporation\\NVSMI\\nvidia-smi.exe" % os.environ['systemdrive']
    else:
        nvidia_smi = "nvidia-smi"
	
    # Get ID, processing and memory utilization for all GPUs
    try:
        p = Popen([nvidia_smi,"--query-gpu=index,uuid,utilization.gpu,memory.total,memory.used,memory.free,driver_version,name,gpu_serial,display_active,display_mode,temperature.gpu", "--format=csv,noheader,nounits"], 
                  stdout=PIPE, creationflags=creationflags)
        stdout, stderror = p.communicate()
    except:
        return []
    output = stdout.decode('UTF-8')
    # output = output[2:-1] # Remove b' and ' from string added by python
    #print(output)
    ## Parse output
    # Split on line break
    lines = output.split(os.linesep)
    #print(lines)
    numDevices = len(lines)-1
    GPUs = []
    for g in range(numDevices):
        line = lines[g]
        #print(line)
        vals = line.split(', ')
        #print(vals)
        for i in range(12):
            # print(vals[i])
            if (i == 0):
                deviceIds = int(vals[i])
            elif (i == 1):
                uuid = vals[i]
            elif (i == 2):
                gpuUtil = safeFloatCast(vals[i])/100
            elif (i == 3):
                memTotal = safeFloatCast(vals[i])
            elif (i == 4):
                memUsed = safeFloatCast(vals[i])
            elif (i == 5):
                memFree = safeFloatCast(vals[i])
            elif (i == 6):
                driver = vals[i]
            elif (i == 7):
                gpu_name = vals[i]
            elif (i == 8):
                serial = vals[i]
            elif (i == 9):
                display_active = vals[i]
            elif (i == 10):
                display_mode = vals[i]
            elif (i == 11):
                temp_gpu = safeFloatCast(vals[i]);
        GPUs.append(GPU(deviceIds, uuid, gpuUtil, memTotal, memUsed, memFree, driver, gpu_name, serial, display_mode, display_active, temp_gpu))
    return GPUs  # (deviceIds, gpuUtil, memUtil)




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
    import torch
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
    from safetensors import safe_open
    
    tensors = {}
    with safe_open(model_file, framework="pt", device='cpu') as f:
        for k in f.keys():
            tensors[k] = f.get_tensor(k)
    return tensors
