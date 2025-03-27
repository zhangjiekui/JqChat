import logging
import os
from jqcode.jq_config.general_config import logfile_path,if_log_verbose
import multiprocessing 
import warnings
warnings.filterwarnings("ignore")
warnings.filterwarnings('ignore',message='unstructured',append=True) 
warnings.filterwarnings('ignore',message='profiles',append=True) 
warnings.filterwarnings('ignore',message='datasets',module='datasets',append=True) 
warnings.filterwarnings('ignore',message='PyTorch',module='datasets',append=True) 
  


VERBOSE = if_log_verbose()
logfile_path = logfile_path
stem = logfile_path.stem


        
class jqkj_logger(logging.Logger):
    def __init__(self,current_file_path=None,logfile_path = logfile_path,verbose=VERBOSE,propagate = False):
        if current_file_path is None:
            current_file_path = __file__        
        try:
            index=current_file_path.index(stem)
            current_file_path = current_file_path[index:]
        except: 
            current_file_path = os.path.basename(current_file_path) 
        current_file_path=f"jqlogger( {current_file_path} "
        super().__init__(name="jqlogger")
        self.propagate=propagate
        self.logger = logging.getLogger(current_file_path)
        self.logger.parent = self
        self.verbose = verbose

        self.lf = logging.FileHandler(logfile_path,mode='w',encoding='utf-8')  # 打印到文件
        self.sm = logging.StreamHandler()  # 打印到终端
        # Formatter对象：日志格式
        formmater1 = logging.Formatter('%(message)s  [%(asctime)s %(levelname)s:%(name)s(%(lineno)d)]',datefmt='%Y-%m-%d %H:%M')
        # %(levelname)s:%(name)s(%(lineno)d)
        formmater2 = logging.Formatter(f'%(message)s  [%(levelname)s:{current_file_path}第%(lineno)d行)]')
        # 为Handler对象绑定格式
        self.lf.setFormatter(formmater1)
        self.sm.setFormatter(formmater2)

        # 将Handler添加给logger并设置日志级别
        self.logger.addHandler(self.lf)
        self.logger.addHandler(self.sm)

        # 设置日志级别，可以在两个关卡进行设置logger与handler
        # logger是第一级过滤，然后才能到handler
        '''
            critical=50
            error =40
            warning =30
            info = 20
            debug =10
        '''
        level = 10 if self.verbose else 30
        self.logger.setLevel(level)
        self.disable_third_parties_logging()

    def disable_third_parties_logging(self):
        for log_name, log_obj in logging.Logger.manager.loggerDict.items():
            if not log_name.lower().startswith('jqlogger'):            
                try:
                    log_obj.setLevel(logging.ERROR)
                    # log_obj.disabled = True
                except:
                    pass

    def get_logger(self):
        return self.logger
    
    def debug(self,message):        
        if self.verbose:
            self.logger.debug(message)
    
    def info(self,message):
        if self.verbose:
            self.logger.info(message)

    def warning(self,message,verbose=True):
        if is_main_process():
            self.logger.warning(message)

    def error(self,message,verbose=True):
        if is_main_process():
            self.logger.error(message)

    def critical(self,message,verbose=True):
        if is_main_process():
            self.logger.error(message)

def is_main_process(pid=None):
    if pid is None:
        pid = os.getpid()  # 获取当前进程的PID
    try:
        # 尝试获取父进程的PID
        parent_pid = os.getppid()
        # 如果父进程的PID与当前进程的PID相同，则当前进程是主进程
        return pid == parent_pid
    except Exception:
        # 如果无法获取父进程的PID（例如，在Windows上），则当前进程可能是主进程
        return True

def _set_multiprocessing_context(mp:multiprocessing=multiprocessing ,context:str="spawn",logger=jqkj_logger(__file__).get_logger()):
    try:
        mp.set_start_method(context)
        logger.warning(f'已成功设置mp.set_start_method("{context}")，后面如果再次尝试设置会try...catch打印报错信息，可忽略')
    except Exception as e:
        logger.debug(f'仅提醒，可忽略：mp.set_start_method("{context}") error:{e}')        
    finally:
        current_method = mp.get_start_method()
        logger.debug(f'Current multiprocessing start method:{current_method}') # 获取当前启动多进程的方法

def set_multiprocessing_context(mp:multiprocessing=multiprocessing ,context:str="spawn",logger=jqkj_logger(__file__).get_logger()):
    try:
        mp.set_start_method(context)
        current_method = mp.get_start_method()
        assert current_method==context, f'设置multiprocessing.set_start_method("{context}")，multiprocessing当前{current_method=}'
        logger.warning(f'已成功设置multiprocessing.set_start_method("{current_method}")')
    except Exception as e:
        pass
          
if __name__ == "__main__":

    # 7、测试
    logger = jqkj_logger().logger
    logger.debug('debug')
    logger.info('info')
    logger.warning('warning')
    logger.error('error')
    logger.critical('critical')
