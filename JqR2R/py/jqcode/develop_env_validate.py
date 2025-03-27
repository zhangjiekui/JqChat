# from multiprocessing.spawn import freeze_support
import sys
from multiprocessing import freeze_support
import torch
from pynvml import *


if __name__ == '__main__':
    if sys.platform.startswith('win'):
        # Hack for multiprocessing.freeze_support() to work from a
        # setuptools-generated entry point.
        freeze_support()

    # import paddle
    # paddle.utils.run_check()
    # print(paddle.ones([3,3]))
    
    # import torch
    print("torch.cuda.is_available:",torch.cuda.is_available())
    print("torch.backends.cudnn.version:",torch.backends.cudnn.version())


    nvmlInit()
    print(f"Driver Version: {nvmlSystemGetDriverVersion()}")
    deviceCount = nvmlDeviceGetCount()
    for i in range(deviceCount):
        handle = nvmlDeviceGetHandleByIndex(i)
        print(f"Device {i} : {nvmlDeviceGetName(handle)}")


