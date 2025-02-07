"""

对源特征进行检索
"""
import faiss

from pybragi.base import log
from datetime import datetime
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "7"
import logging

import parselmouth
import torch

# import torchcrepe
from time import time as ttime

# import pyworld
import librosa
import numpy as np
import soundfile as sf
import torch.nn.functional as F
from fairseq import checkpoint_utils

# from models import SynthesizerTrn256#hifigan_nonsf
# from lib.infer_pack.models import SynthesizerTrn256NSF as SynthesizerTrn256#hifigan_nsf
from infer.lib.infer_pack.models import (
    SynthesizerTrnMs256NSFsid as SynthesizerTrn256,
    SynthesizerTrnMs256NSFsid, SynthesizerTrnMs256NSFsid_nono
)  # hifigan_nsf
from scipy.io import wavfile

# from lib.infer_pack.models import SynthesizerTrnMs256NSFsid_sim as SynthesizerTrn256#hifigan_nsf
# from models import SynthesizerTrn256NSFsim as SynthesizerTrn256#hifigan_nsf
# from models import SynthesizerTrn256NSFsimFlow as SynthesizerTrn256#hifigan_nsf


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
hubert_path = r"Retrieval-based-Voice-Conversion-WebUI/assets/hubert/hubert_base.pt"  #
logging.info("Load model(s) from {}".format(hubert_path))
models, saved_cfg, task = checkpoint_utils.load_model_ensemble_and_task(
    [hubert_path],
    suffix="",
)
model = models[0]
model = model.to(device)
model = model.half()
model.eval()



is_half=True
model_path = "Retrieval-based-Voice-Conversion-WebUI/assets/weights/kuohao-rvc/kuohao.pth"
cpt = torch.load(model_path, map_location="cpu")
tgt_sr = cpt["config"][-1]
cpt["config"][-3]=cpt["weight"]["emb_g.weight"].shape[0]#n_spk
if_f0=cpt.get("f0",1)
if(if_f0==1):
    net_g = SynthesizerTrnMs256NSFsid(*cpt["config"], is_half=is_half)
else:
    net_g = SynthesizerTrnMs256NSFsid_nono(*cpt["config"])
del net_g.enc_q

"""
net_g = SynthesizerTrn256(
    spec_channels=1025,
    segment_size=1024,
    inter_channels=192,
    hidden_channels=192,
    filter_channels=768,
    n_layers=2,
    n_layers_k=6,
    kernel_size=3,
    p_dropout=0,
    resblock="1",
    resblock_kernel_sizes=[3, 7, 11],
    upsample_rates=[10, 10, 2, 2],
    upsample_initial_channel=512,
    upsample_kernel_sizes=[16, 16, 4, 4],
    gin_channels=183,
    sr=256,
    is_half=True,
)
weights = torch.load("Retrieval-based-Voice-Conversion-WebUI/assets/weights/kuohao-rvc/kuohao.pth")
logging.debug(net_g.load_state_dict(weights, strict=True))
"""

net_g.eval().to(device)
net_g.half()


def get_f0(x, p_len, f0_up_key=0):
    time_step = 160 / 16000 * 1000
    f0_min = 50
    f0_max = 1100
    f0_mel_min = 1127 * np.log(1 + f0_min / 700)
    f0_mel_max = 1127 * np.log(1 + f0_max / 700)

    f0 = (
        parselmouth.Sound(x, 16000)
        .to_pitch_ac(
            time_step=time_step / 1000,
            voicing_threshold=0.6,
            pitch_floor=f0_min,
            pitch_ceiling=f0_max,
        )
        .selected_array["frequency"]
    )

    pad_size = (p_len - len(f0) + 1) // 2
    if pad_size > 0 or p_len - len(f0) - pad_size > 0:
        f0 = np.pad(f0, [[pad_size, p_len - len(f0) - pad_size]], mode="constant")
    f0 *= pow(2, f0_up_key / 12)
    f0bak = f0.copy()

    f0_mel = 1127 * np.log(1 + f0 / 700)
    f0_mel[f0_mel > 0] = (f0_mel[f0_mel > 0] - f0_mel_min) * 254 / (
        f0_mel_max - f0_mel_min
    ) + 1
    f0_mel[f0_mel <= 1] = 1
    f0_mel[f0_mel > 255] = 255
    # f0_mel[f0_mel > 188] = 188
    f0_coarse = np.rint(f0_mel).astype(np.int32)
    return f0_coarse, f0bak

index_rate = 0.88

logging.info("Load model(s) from {}".format(index_rate))
logging.info("Load model(s) from {}".format(index_rate))

index = faiss.read_index("Retrieval-based-Voice-Conversion-WebUI/assets/weights/kuohao-rvc/added_IVF256_Flat_nprobe_1_kuohao_v1.index")
# big_npy = np.load("Retrieval-based-Voice-Conversion-WebUI/logs/mute/3_feature256/mute.npy")
# big_npy = np.load("Retrieval-based-Voice-Conversion-WebUI/logs/mute/3_feature768/mute.npy")
big_npy = index.reconstruct_n(0, index.ntotal)

ta0 = ta1 = ta2 = 0
for idx, name in enumerate(
    [
        "Retrieval-based-Voice-Conversion-WebUI/assets/weights/some_voice/audios_unchico.mp3",
    ]
):  ##
    f0_up_key = -2  #
    audio, sampling_rate = sf.read(name)
    if len(audio.shape) > 1:
        audio = librosa.to_mono(audio.transpose(1, 0))
    if sampling_rate != 16000:
        audio = librosa.resample(audio, orig_sr=sampling_rate, target_sr=16000)

    feats = torch.from_numpy(audio).float()
    if feats.dim() == 2:  # double channels
        feats = feats.mean(-1)
    assert feats.dim() == 1, feats.dim()
    feats = feats.view(1, -1)
    padding_mask = torch.BoolTensor(feats.shape).fill_(False)
    inputs = {
        "source": feats.half().to(device),
        "padding_mask": padding_mask.to(device),
        "output_layer": 9,  # layer 9
    }
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    t0 = ttime()
    with torch.no_grad():
        logits = model.extract_features(**inputs)
        feats = model.final_proj(logits[0])

    ####索引优化
    npy = feats[0].cpu().numpy()
    if is_half:
        npy = npy.astype("float32")

    # _, I = index.search(npy, 1)
    # npy = big_npy[I.squeeze()]

    score, ix = index.search(npy, k=8)
    weight = np.square(1 / score)
    weight /= weight.sum(axis=1, keepdims=True)
    npy = np.sum(big_npy[ix] * np.expand_dims(weight, axis=2), axis=1)

    if is_half:
        npy = npy.astype("float16")
    feats = (
        torch.from_numpy(npy).unsqueeze(0).to(device) * index_rate
        + (1 - index_rate) * feats
    )

    feats = F.interpolate(feats.permute(0, 2, 1), scale_factor=2).permute(0, 2, 1)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    t1 = ttime()
    # p_len = min(feats.shape[1],10000,pitch.shape[0])#太大了爆显存
    p_len = min(feats.shape[1], 10000)  #
    pitch, pitchf = get_f0(audio, p_len, f0_up_key)
    p_len = min(feats.shape[1], 10000, pitch.shape[0])  # 太大了爆显存
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    t2 = ttime()
    feats = feats[:, :p_len, :]
    pitch = pitch[:p_len]
    pitchf = pitchf[:p_len]
    p_len = torch.LongTensor([p_len]).to(device)
    pitch = torch.LongTensor(pitch).unsqueeze(0).to(device)
    sid = torch.LongTensor([0]).to(device)
    pitchf = torch.FloatTensor(pitchf).unsqueeze(0).to(device)
    with torch.no_grad():
        audio = (
            net_g.infer(feats, p_len, pitch, pitchf, sid)[0][0, 0]
            .data.cpu()
            .float()
            .numpy()
        )  # nsf
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    t3 = ttime()
    ta0 += t1 - t0
    ta1 += t2 - t1
    ta2 += t3 - t2
    logging.info(f"{ta0:.2f}s {ta1:.2f}s {ta2:.2f}s")
    # wavfile.write("ft-mi_1k-index256-noD-%s.wav"%name, 40000, audio)##
    # wavfile.write("ft-mi-freeze-vocoder-flow-enc_q_1k-%s.wav"%name, 40000, audio)##
    # wavfile.write("ft-mi-sim1k-%s.wav"%name, 40000, audio)##
    wavfile.write(f"output/{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.wav", 40000, audio)  ##


logging.info(f"{ta0:.2f}s {ta1:.2f}s {ta2:.2f}s")

import time
time.sleep(0.1)
