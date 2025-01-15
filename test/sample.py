
import copy
import glob
voices_dir = "/cano_nas01/workspace/online/audio/some_wav/*.wav"
voices = glob.glob(voices_dir)
print(voices)


from lib.vc.utils import (
    load_hubert,
    HubertModelQueue
)
from lib.config.config import Config
from fairseq.models.hubert.hubert import HubertModel

def deep_copy_hubert(model: HubertModel) -> HubertModel:
    """Creates a deep copy of a HubertModel instance"""
    # Deep copy the config and task
    cfg_copy = copy.deepcopy(model.cfg)
    task_copy = copy.deepcopy(model.task)
    
    # Create new model instance
    new_model = HubertModel.build_model(cfg_copy, task_copy)
    
    # Copy state dict to new model
    new_model.load_state_dict(model.state_dict())
    
    # Ensure same device as original
    device = next(model.parameters()).device
    new_model = new_model.to(device)
    
    return new_model

config = Config()

hubert_model: HubertModel = load_hubert(config)
hubert_model_copy = deep_copy_hubert(hubert_model)


print(hubert_model)
print(hubert_model_copy)
