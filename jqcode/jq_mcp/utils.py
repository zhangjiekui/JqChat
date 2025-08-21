import threading
from jqcode.langgraph_in_class import GraphAgent
from jqcode.jq_queue.jq_queues import JqFileSystemQueue
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()
class ThreadWithResult(threading.Thread):  
    def __init__(self, target, args=()):  
        super(ThreadWithResult, self).__init__()  
        self.func = target  
        self.args = args
        self.result = ""  
    def run(self):
        try:  
            self.result = self.func(*self.args)  # 在执行函数的同时，把结果赋值给result,  
        except:
            self.result = self.func(self.args)
        finally:
            if self.result:
                logger.debug(self.result)
            else:
                logger.warning("没有结果")
                self.result = ""  
    # 然后通过get_result函数获取返回的结果
    def get_result(self):  
        try:  
            return self.result  
        except Exception as e:  
            return None 
def get_process_text(jq_queque:JqFileSystemQueue,t:ThreadWithResult,streaming=True,
                     leading_text:str = '<details>\n<summary>点击查看"整体执行过程"</summary>\n<font color="grey">\n',
                     ending_text:str = '\n<br></font></details>\n------\n',
                     process_ending_text:str = "DONE"):
        if streaming:
            yield leading_text 
        text_string = leading_text  
        values = [] 
        chat_result_list = []      
        condition = True
        accumulate_size :int = 0
        current_no :int = 0
        while condition:            
            try:
                size = jq_queque.size()
                values =jq_queque.dequeue()
                if values:
                    for j,text in enumerate(values):
                        if text.strip() == process_ending_text:
                            condition = False
                            jq_queque.clear()
                        current_no = accumulate_size+j+1
                        text = f"\n {current_no}. " + text
                        logger.debug(f"{accumulate_size=},{size=},{j=} {text}")
                        if streaming:
                            yield text
                        text_string += text
                    accumulate_size += size
            except Exception as e:
                condition = False
                logger.warning(f"获取执行过程信息时：{e}")
                _text = "执行过程信息时出现意外，跳过" 
                text = f"\n {current_no + 1}. "+_text
                if streaming:
                    yield text
                else:
                    text_string += text
                jq_queque.clear()
                break
            
        t.join()
        if streaming:
            yield ending_text
            # yield  "\n<br>"
        else:
            text_string +=ending_text
            # text_string += "\n<br>"
        
        chat_result_list = t.get_result()
        if chat_result_list:
            if streaming:
                for result in chat_result_list:
                    chunks = [result[i:i+1024] for i in range(0, len(result), 1024)]
                    for chunk in chunks:
                        # await asyncio.sleep(0.1)  # 模拟数据处理时间
                        yield chunk
                        
                    # yield result

        if not streaming:
            results = [text_string]
            if chat_result_list:
                results = [text_string] + chat_result_list
            return results
def chat(chat_bot:GraphAgent, user_question:str,only_return_answer_text:bool=False):      
    results_list = chat_bot.run_conversation(user_question=user_question,only_return_answer_text=only_return_answer_text)
    return results_list

