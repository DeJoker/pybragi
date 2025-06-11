import logging
import numpy as np
from scipy import signal
import os
import traceback
import requests
from io import BytesIO


def convert_float32_to_int16(float32_array: np.ndarray) -> np.ndarray:
    """
    Convert a float32 numpy array (assumed to be normalized to -1.0 to 1.0) to int16.
    """
    if not isinstance(float32_array, np.ndarray) or float32_array.dtype != np.float32:
        raise ValueError("Input array must be a numpy array of type float32")

    # Clip to ensure input is within [-1.0, 1.0] before scaling.
    # soundfile.read(dtype='float32') should already provide data in this range.
    float32_array = np.clip(float32_array, -1.0, 1.0)
    
    # Scale to the int16 range.
    # The maximum positive value for int16 is 32767 (2^15 - 1).
    # This maps 1.0f to 32767 and -1.0f to -32767.
    scaled_array = float32_array * 32767.0
    
    # Convert to int16. Values are truncated (e.g., 32767.9 becomes 32767).
    int16_array = scaled_array.astype(np.int16)
    return int16_array

def convert_int16_to_float32(int16_array: np.ndarray) -> np.ndarray:
    """
    Convert an int16 numpy array to float32 (normalized to -1.0 to 1.0).
    """
    if not isinstance(int16_array, np.ndarray) or int16_array.dtype != np.int16:
        raise ValueError("Input array must be a numpy array of type int16")
    
    # Convert to float32 and normalize.
    # Dividing by 32768.0 maps the int16 range [-32768, 32767]
    # to approximately [-1.0, 1.0). Specifically, -32768 maps to -1.0,
    # and 32767 maps to 32767/32768.0 (approx. 0.999969).
    float32_array = int16_array.astype(np.float32) / 32768.0
    return float32_array


def resample(input_data: bytes, np_type, origin_rate, target_rate):
    """
    Resample PCM audio data from network input.
    
    Args:
        input_data (bytes): Raw PCM audio data
        np_type: Input data type (e.g., np.int16)
        origin_rate (int): Original sample rate (e.g., 16000)
        target_np_type: Target data type (e.g., np.float32)
        target_rate (int): Target sample rate
    
    Returns:
        bytes: Resampled audio data in target format
    """
    # Convert bytes to numpy array
    audio_np = np.frombuffer(input_data, dtype=np_type)
    # logging.info(f"origin audio: {audio_np.shape} {audio_np.dtype} {audio_np.max()} {audio_np.min()}, duration: {len(audio_np)/origin_rate}")
    
    # Calculate number of samples for target rate
    num_samples = int(len(audio_np) * target_rate / origin_rate)
    
    # Resample the audio
    resampled_audio_np = signal.resample(audio_np, num_samples)
    # logging.info(f"resample audio: {resampled_audio_np.shape} {resampled_audio_np.dtype} {resampled_audio_np.max()} {resampled_audio_np.min()}, duration: {len(resampled_audio_np)/target_rate}")
    resampled_audio_np = resampled_audio_np.astype(np_type)
    
    return resampled_audio_np


def audio2(i, o, format, sr):
    import av
    inp = av.open(i, "r")
    out = av.open(o, "w", format=format)
    if format == "ogg":
        format = "libvorbis"
    if format == "f32le":
        format = "pcm_f32le"

    ostream = out.add_stream(format, channels=1)
    ostream.sample_rate = sr

    for frame in inp.decode(audio=0):
        for p in ostream.encode(frame):
            out.mux(p)

    out.close()
    inp.close()

def load_audio(file, sr):
    file = (
        file.strip(" ").strip('"').strip("\n").strip('"').strip(" ")
    )  # 防止小白拷路径头尾带了空格和"和回车
    if os.path.exists(file) == False:
        raise RuntimeError(
            "You input a wrong audio path that does not exists, please fix it!"
        )
    try:
        with open(file, "rb") as f:
            with BytesIO() as out:
                audio2(f, out, "f32le", sr)
                return np.frombuffer(out.getvalue(), np.float32).flatten()
    except:
        traceback.format_exc()
        return None

def load_audio_from_url(url: str, sr: int):
    try:
        with requests.get(url) as r:
            with BytesIO() as out:
                if not r.content:
                    logging.error(f"empty content: {url}")
                    raise RuntimeError("empty content")
                audio2(BytesIO(r.content), out, "f32le", sr)
                return np.frombuffer(out.getvalue(), np.float32).flatten()
    except:
        traceback.format_exc()
        logging.error(f"load failed: {url}")


def resample_librosa(audio, origin_rate, target_rate):
    import librosa
    return librosa.resample(audio, orig_sr=origin_rate, target_sr=target_rate)

if __name__ == "__main__":
    print(load_audio_from_url("http://zyvideo101.oss-cn-shanghai.aliyuncs.com/zyad/73/0c/201a-cd10-11ef-bdec-00163e023ce8", 16000))

