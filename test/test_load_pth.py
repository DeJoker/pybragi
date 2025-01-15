import torch
from pybragi.base import log
import logging
from pybragi.llm import model_utils
dicts = {}
# dicts = torch.load("Retrieval-based-Voice-Conversion-WebUI/assets/uvr5_weights/HP2_all_vocals.pth")

# dicts = torch.load("Retrieval-based-Voice-Conversion-WebUI/assets/hubert/hubert_inputs.pth")

# dicts = torch.load("Retrieval-based-Voice-Conversion-WebUI/assets/rmvpe/rmvpe.pt")

# dicts = torch.load("Retrieval-based-Voice-Conversion-WebUI/assets/uvr5_weights/VR-DeEchoAggressive.pth")
# dicts = torch.load("Retrieval-based-Voice-Conversion-WebUI/assets/Synthesizer_inputs.pth")
model_utils.dicts_parameters(dicts, show_info=True)

# dicts = torch.load("Retrieval-based-Voice-Conversion-WebUI/assets/hubert/hubert_base.pt", map_location=torch.device("cpu")) # bad
# dicts = torch.load("Retrieval-based-Voice-Conversion-WebUI/assets/pretrained/D32k.pth")
# dicts = torch.load("Retrieval-based-Voice-Conversion-WebUI/assets/pretrained_v2/D40k.pth")
# model_utils.dicts_parameters(dicts.get("model"), show_info=True)

# dicts = torch.load("Retrieval-based-Voice-Conversion-WebUI/assets/weights/白菜357k.pt")
# dicts.get("dv")  torch.Size([1, 256])
# model_utils.dicts_parameters(dicts.get("weight"), show_info=True)



import faiss
index = faiss.read_index("Retrieval-based-Voice-Conversion-WebUI/assets/weights/樱花-rvc/added_IVF256_Flat_nprobe_1_loliyinghua_v1.index")
print(index)

# logging.info(dicts)
