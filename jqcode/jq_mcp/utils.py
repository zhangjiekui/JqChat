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
            try:
                self.result = self.func(self.args)
            except Exception as e:
                self.result = ""
                logger.error(f"运行出现错误:{e}")
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
        
def get_process_text(jq_queque:JqFileSystemQueue,t:ThreadWithResult,num_per_chunk = 512,
                     leading_text:str = '<details open>\n<summary>点击查看"整体执行过程"</summary>\n\n',
                     ending_text:str = '\n</details>\n\n------\n',
                     process_ending_text:str = "DONE"):


        yield leading_text
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
                        yield text
                    accumulate_size += size
            except Exception as e:
                condition = False
                logger.warning(f"获取执行过程信息时：{e}")
                _text = "执行过程信息时出现意外，跳过"
                text = f"\n {current_no + 1}. "+_text
                yield text
                jq_queque.clear()
                break

        t.join()
        yield ending_text
        # yield  "\n<br>"

        chat_result_list = t.get_result()

        if chat_result_list:
            for index,result in enumerate(chat_result_list):
                logger.warning(f"chat_result_list[{index}]: {result=}")
                chunks = [result[i:i+num_per_chunk] for i in range(0, len(result), num_per_chunk)]
                for chunk in chunks:
                    # await asyncio.sleep(0.1)  # 模拟数据处理时间
                    yield chunk


def _get_process_text(jq_queque:JqFileSystemQueue,t:ThreadWithResult,streaming=True,num_per_chunk = 512,
                     leading_text:str = '<details open>\n<summary>点击查看"整体执行过程"</summary>\n\n',
                     ending_text:str = '\n</details>\n\n------\n',
                     process_ending_text:str = "DONE"):

        # 添加调试日志
        logger.warning(f">>> get_process_text 被调用，streaming={streaming}, type={type(streaming)}")

        # 关键修复：非流式模式下直接返回列表，不走生成器逻辑
        if not streaming:
            text_string = leading_text
            values = []
            chat_result_list = []
            condition = True
            accumulate_size = 0
            current_no = 0

            while condition:
                try:
                    size = jq_queque.size()
                    values = jq_queque.dequeue()
                    if values:
                        for j, text in enumerate(values):
                            if text.strip() == process_ending_text:
                                condition = False
                                jq_queque.clear()
                            current_no = accumulate_size + j + 1
                            text = f"\n {current_no}. " + text
                            logger.debug(f"{accumulate_size=},{size=},{j=} {text}")
                            text_string += text
                        accumulate_size += size
                except Exception as e:
                    condition = False
                    logger.warning(f"获取执行过程信息时：{e}")
                    _text = "执行过程信息时出现意外，跳过"
                    text = f"\n {current_no + 1}. " + _text
                    text_string += text
                    jq_queque.clear()
                    break

            t.join()
            text_string += ending_text

            chat_result_list = t.get_result()
            # if chat_result_list:
            #     logger.warning(f"chat_result_list: {chat_result_list}")

            results = [text_string]
            if chat_result_list:
                results = [text_string] + chat_result_list
            text = "\n".join(results)
            # logger.warning(f"最终结果: {text}")
            for value in results:
                if value.strip():
                    # logger.warning(f"结果值: {value[:200]}...")  # 调试输出每个值的前200字符
                    yield value
            # return results

        # 流式模式：使用生成器
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
                for index,result in enumerate(chat_result_list):
                    logger.warning(f"chat_result_list[{index}]: {result=}")
                    chunks = [result[i:i+num_per_chunk] for i in range(0, len(result), num_per_chunk)]
                    for chunk in chunks:
                        # await asyncio.sleep(0.1)  # 模拟数据处理时间
                        yield chunk

                    # yield result
def chat(chat_bot:GraphAgent, user_question:str,only_return_answer_text:bool=False):      
    results_list = chat_bot.run_conversation(user_question=user_question,only_return_answer_text=only_return_answer_text)
    return results_list

