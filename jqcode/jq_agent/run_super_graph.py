import sys
project_root_path = '/data/projects/JqChat'
p1 = '/data/projects/JqChat/jqcode'
p2 = '/data/projects/JqChat/jqcode/jq_agent'
for p in [project_root_path, p1, p2]:
    sys.path.append(p)

from langchain_core.messages import HumanMessage,ToolMessage,AIMessage
# from jqcode.jq_agent.hierarchical_teams_supervisor_examples.super_graph import super_graph_compiled
from super_graph_builder import super_graph
from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver
from langgraph.pregel import GraphRecursionError
import asyncio
# from langchain_core.messages import BaseMessage, HumanMessage,SystemMessage,ToolMessage

question1 = "Write a brief research report on the North American sturgeon. Include a chart."
# question ="写一份安徽晶奇公司的研究报告，包括图表。记住，你拥有可以上网、执行python代码和绘制图表的工具能力"
question2 ="请首先搜索安徽晶奇公司的相关信息，并根据这些信息写一份安徽晶奇公司的简要介绍。"
question3 ="请搜索中国科学技术大学的信息，并写一份中国科学技术大学的简要介绍材料。"
question4 ="请查询后天从合肥到上海的航班。"
question5 ="请使用python工具计算1到100的和。"
question ="合肥八中有多少个校区？"
qs = [question1,question2,]
qs = [question1,question2,question3,question4,question5,question]
qs = []
# qs = [question5]

super_graph_compiled =  super_graph.compile()

i=1
for question in qs: 
    print('===========================================================================================================')
    print(f"question{i}:{question}")
    i=i+1
    print('===========================================================================================================')
    
    for s in super_graph_compiled.stream(
        {"messages": [HumanMessage(content=question)],"question":question},
        config = {"recursion_limit":25,"configurable": {"thread_id": "userid-session_id"}},
        debug = False
    ):
        # if "__end__" not in s:
        try:
            supervisor = s.get('supervisor',None)
            next = supervisor.get('next',None)
            if next == "FINISH":
                messages = supervisor.get('messages',None)
                last_message = messages[-1]
                if isinstance(last_message,(ToolMessage,AIMessage)):
                    print("~~~输出最终执行结果~~~")
                    print(f"用户问题：{supervisor['question']}")
                    print(f"最后答案：{last_message.content}")
                    print("~~~输出最终执行结果~~~")
                # else:
                #     print("---执行中间过程---")
                #     print(s)
                #     print("---执行中间过程---")                

        except:
            pass
            # print("---执行中间过程---")
            # print(s)
            # print("---执行中间过程---")



        # if "FINISH" not in s:
        #     print(s)
        #     print("---")\

# aRun
# async def main():
#     asyncio.create_task(long_running_task())
# async def arun_super_graph(question:str,config = {"recursion_limit":25,"configurable": {"thread_id": "userid-sessionid_981"}}):
def arun_super_graph(question:str,config = {"recursion_limit":25,"configurable": {"thread_id": "userid-sessionid_97877"}}):
    async_memory = AsyncSqliteSaver.from_conn_string("checkpoints.async_sqlite")
    super_graph_compiled_async = super_graph.compile(checkpointer=async_memory)

    print('=*='*20)
    print(f"In Agent 'arun_graph_workflow'：{question=}")
    if question=="你知道我叫什么吗？":
        pass
    inputs = {"messages": [HumanMessage(content=question)],"question":question,"next":None}

    result = None
    
    try:
        # value = await super_graph_compiled_async.ainvoke(inputs, config)

        coro = super_graph_compiled_async.ainvoke(inputs, config)
        value = asyncio.run(coro)
        condidate_keys = ['supervisor']
        
        for key in condidate_keys:
            if key in value.keys():
                value = value.get('supervisor',None)
        next = value.get('next',None)
        # print(next)
        messages = value.get('messages',None)
        last_message = messages[-1]
        # print(type(last_message))
        # print(f"{last_message.content=}")        
        if next == "FINISH":
            if isinstance(last_message,(ToolMessage,AIMessage)):
                print("~~~输出最终执行结果~~~")
                print(f"用户问题：{value['question']}")
                result = last_message.content
                if '\nFinal Answer:' in result and '\nAction:' in result:
                    _index0 = result.rindex('\nFinal Answer:')
                    _index1 = result.rindex('\nAction:')
                    result = result[_index0:_index1].replace('\nFinal Answer:','')
                elif '\nFinal Answer:' in result:
                    _index0 = result.rindex('\nFinal Answer:')
                    result = result[_index0:].replace('\nFinal Answer:','')

                print(f"最后答案：{result}")
                print("~~~输出最终执行结果~~~")
                # asyncio.get_running_loop().stop()
                return result
            else:
                pass
    # except:
    #     pass   
    # try:
    #     result = None
    #     while not result:
    #         value = await super_graph_compiled_async.ainvoke(inputs, config)           

    #         try:
    #             print(value.keys())
    #             condidate_keys = ['supervisor']
                
    #             for key in condidate_keys:
    #                 if key in value.keys():
    #                     value = value.get('supervisor',None)
    #             next = value.get('next',None)
    #             if next == "FINISH":
    #                 messages = value.get('messages',None)
    #                 last_message = messages[-1]
    #                 if isinstance(last_message,(ToolMessage,AIMessage)):
    #                     print("~~~输出最终执行结果~~~")
    #                     print(f"用户问题：{value['question']}")
    #                     result = last_message.content
    #                     print(f"最后答案：{last_message.content}")
    #                     print("~~~输出最终执行结果~~~")
    #                     return result
    #         except:
    #             pass

    #     except Exception as e:
    #         print(e) 
    #         raise e               
            
    except GraphRecursionError:
        print("!!!!!!GraphRecursionError: Graph recursion limit reached.!!!!!!")
        result = 'GraphRecursionError'
        return result
    except Exception as e:
        
        print(f"!!!!!!Error: {e}.!!!!!!")
        result = f'出现了错误，你可以重新输入问题{question}再尝试几次。以下是错误的详细信息:{e}'
        return result


if __name__ == '__main__':

    # WARNING 05-13 17:46:33 scheduler.py:619] Input prompt (74314 tokens) is too long and exceeds limit of 4096
    tool_question = ["请调用工具get_flight_number来查询今天从合肥到上海的航班","请调用工具python_repl_tool来编码计算the 10th fibonacci number并执行和输出结果"]
    print('\n\n')
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5) 
    print("~~~~test_tools~~~~"*5)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5)
    for question in tool_question:
        # result=asyncio.run(arun_super_graph(question))
        # print(result)
        # print(asyncio.run(arun_super_graph(question)))
        print(arun_super_graph(question))

# """       
    print('\n\n')
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5) 
    print("~~~~test_memory~~~~"*5)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5)
    questions_test_memory = ["你知道我叫什么吗？","我叫张结魁，你叫什么呀？我们做好朋友吧","?"] 
    for question in questions_test_memory:
        print(arun_super_graph(question))

    questions = ["What are the types of agent memory?","What player are the Bears expected to draft first in the 2024 NFL draft?","合肥是一个什么样的城市？","Hello, how are you today?"]
    print('\n\n')
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5) 
    print("$$$$run_graph_workflow$$$$"*5)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5) 
    for question in questions:
        print(arun_super_graph(question))
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5)

   