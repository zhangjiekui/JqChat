# pip install pynvml
from pynvml import nvmlInit,nvmlDeviceGetMemoryInfo,nvmlSystemGetDriverVersion,nvmlDeviceGetCount
from pynvml import nvmlDeviceGetHandleByIndex,nvmlDeviceGetHandleByIndex,nvmlDeviceGetName,nvmlDeviceGetTemperature
from pynvml import nvmlDeviceGetPowerState,NVMLError,nvmlShutdown
import math
import torch
import gc

from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

class gpu_management():
    def nvidia_info(self):
        nvidia_dict = {
            "state": True,
            "nvidia_version": "",
            "nvidia_count": 0,
            "gpus": []
        }
        try:
            nvmlInit()
            nvidia_dict["nvidia_version"] = nvmlSystemGetDriverVersion()
            nvidia_dict["nvidia_count"] = nvmlDeviceGetCount()
            for i in range(nvidia_dict["nvidia_count"]):
                handle = nvmlDeviceGetHandleByIndex(i)
                memory_info = nvmlDeviceGetMemoryInfo(handle)
                gpu = {
                    "gpu_name": nvmlDeviceGetName(handle),
                    "total": int(memory_info.total/1024**2),
                    "free": int(memory_info.free/1024**2),
                    "used": int(memory_info.used/1024**2),
                    "temperature": f"{nvmlDeviceGetTemperature(handle, 0)}℃",
                    "powerStatus": nvmlDeviceGetPowerState(handle)
                }
                nvidia_dict['gpus'].append(gpu)
        except NVMLError as _:
            nvidia_dict["state"] = False
        except Exception as _:
            nvidia_dict["state"] = False
        finally:
            try:
                nvmlShutdown()
            except:
                pass
        return nvidia_dict

    def select_one_gpu_device(self,needed_gpu_memeory=2500,model_message_for_logging=''):
        logger.info('\n=======================查看GPU状态===============================')
        device = -1   

        info = self.nvidia_info()
        gpu_nums = info['nvidia_count']
        logger.info(f"==共有{gpu_nums}块GPU==")
        gpus_free = [0]*gpu_nums

        if gpu_nums:        
            gpus = info['gpus']
            for i, gpu in enumerate(gpus):
                tot = gpu['total']
                used =  gpu['used']
                free =  gpu['free']           
                gpus_free[i] = free
                logger.info(f"    【GPU{i}】 tot: {tot}M, used: {used}M, free: {free}M 使用率：{used/tot*100 :.1f}%")
                free = math.floor(free) #向下取整
                if free > needed_gpu_memeory:
                    device = i
            
            if device == -1:
                d =1 if gpus_free[1]>=gpus_free[0] else 0
                
                logger.info(f"==  GPU显存紧张（正常需要{needed_gpu_memeory}M），当前空余显存最大的GPU{d}，也仅余{gpus_free[d]}M。")
                logger.info(f"==  自动选用CPU执行，但运行速度会慢一些。")
            else:
                    logger.info(f"    当前选用了GPU{device}执行，显存充分。")

        else:
            logger.info(f"==  未发现GPU，或GPU工作不正常！请上报管理员。自动选用CPU执行，但运行速度会慢一些。")
            device = -1
            logger.info(f'=============================现在Device({device})上执行{model_message_for_logging}操作====================================\n')
        logger.info('=======================查看GPU状态===============================')
        return device

    def is_qualified_gpu_device_for_torch(self,device="cuda:0"):

        if isinstance(device, torch.device):
            if device.type == 'cuda':
                return True
            else:
                return False    
        
        gup_info = self.nvidia_info()
        gpu_nums = gup_info['nvidia_count']
        if isinstance(device, str):
            try:
                _num = device.split(':')[-1]
                _num = int(_num)
                device = _num
            except:
                logger.error(f'输入的device字符串{device}不正确，无法转换为int值')
                return False

        if isinstance(device, int):
            if device in list(range(gpu_nums)):
                return True
            else:
                return False
                                
    def torch_gc(self,device="cuda:1"):
        """
        清除Pytorch GPU缓存
        device参数:
            str:如"cuda:0"、"cuda:1"
            int:如0,1
            torch.device:已经实例化的对象  
        """

        if self.is_qualified_gpu_device_for_torch(device):
            device = torch.device(device)
            with torch.cuda.device(device):
                torch.cuda.empty_cache() # 清空PyTorch的CUDA缓存
                torch.cuda.ipc_collect() # 收集CUDA垃圾
                gc.collect()             # 强制进行一次垃圾回收

                logger.info(f'请在调用torch_gc方法前，请先使用del model(实例)，以释放显存。')
                logger.info(f'已成功清理[{device}]上Pytorch的显存占用。')
        else:
            logger.warning(f'要清理的GPU设备[{device}]不存在，跳过，没有执行真正的Pytorch显存清理操作！')
    
    
    def paddle_gc(self):

        """
        清除Paddle GPU缓存
        """       

        try:
            import paddle
            device = paddle.get_device()
            if 'gpu' in device:
                paddle.device.cuda.empty_cache()
                gc.collect()
                logger.info(f'请在调用paddle_gc方法前，请先使用del model(实例)，以释放显存。')
                logger.info(f'已成功清理[{device}]上Paddle的显存占用。')
            else:
                logger.warning(f'要清理的GPU设备[{device}]不存在，跳过，没有执行真正的Paddle显存清理操作！')
        except:
            logger.warning(f'输入的device[{device}]不正确，跳过，没有执行真正的Paddle显存清理操作！')


if __name__ == "__main__":
    
    gc_m = gpu_management()
    device = gc_m.select_one_gpu_device()

   
    gc_m.torch_gc(device="cuda:1" )
    gc_m.torch_gc(device=1 )
    device =torch.device('cpu')
    gc_m.torch_gc(device)
    gc_m.torch_gc(-1)


    print('===================================')
    # import paddle
    # device = paddle.set_device('cpu')
    # gc_m.paddle_gc()
    # device = paddle.set_device('gpu:0')
    # gc_m.paddle_gc()
    # device = paddle.set_device('gpu:1')
    # gc_m.paddle_gc()

