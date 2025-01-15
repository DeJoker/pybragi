from gpu_mem_track import MemTracker
import torch

gpu_tracker = MemTracker()

gpu_tracker.track()
model = YourModel().cuda()
gpu_tracker.track()
input_tensor = torch.randn(1, 3, 224, 224).cuda()
gpu_tracker.track()
output = model(input_tensor)
gpu_tracker.track()
del output
del input_tensor
del model
gpu_tracker.track()
torch.cuda.empty_cache()
gpu_tracker.track()