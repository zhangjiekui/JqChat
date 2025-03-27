import os
# OLLAMA_HOST env setting MUST be done before you import langchain_ollama package in your code.
os.environ['OLLAMA_HOST'] = "http://10.1.150.106:11434"

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from typing import List

# https://python.langchain.com/v0.2/docs/integrations/chat/ollama/
# https://github.com/langchain-ai/langchain/blob/master/docs/docs/integrations/chat/ollama.ipynb
# https://github.com/ollama/ollama/releases/tag/v0.3.0
# https://github.com/langchain-ai/langchain/tree/master/libs/partners/ollama



def get_ollama_chat_model(model_name = "llama3-groq-tool-use:8b-q8_0",temperature=0.5,top_p=0.65, tools:list = None,verbose=True):
    ollama_host = os.getenv("OLLAMA_HOST",'http://localhost:11434')
    ollama_chat_model = ChatOllama(model=model_name,temperature=temperature,top_p=top_p,verbose=verbose)
    print("-------ollama_chat_model详细信息-------")
    print(f'       ==Get ollama_chat_model successfully. model_name={model_name}, ollama_host = {ollama_host}')
    print("-------ollama_chat_model详细信息-------")
    if tools:
        return ollama_chat_model.bind_tools(tools)        
    return ollama_chat_model

model_chat = get_ollama_chat_model(model_name = "mistral-large:latest")


def create_route(members):
    system_prompt = f"""
        Given the user questions, dicide next tool/action should take:{members}\n
        'Tools': Only responsible for tool calls, such as query flight numbers and generate/run python code,\n
        'Rag': Responsible for all other things, such as daily greetings and chatting, search web or knowledge base/vectorstore to answer user's question.
        When finished, respond with action 'FINISH'.
                
        Args:
            next: (str) next action should take, next must be one of {members}.
        """  
    
    def route(next:str) -> bool:
        return True

    route.__doc__ = system_prompt
    return route

route = create_route(members=["Tools", "Rag", "FINISH" ])


model_chat = model_chat.bind_tools([route])
question = "请调用工具查询查询明天从合肥到上海的航班"
response = model_chat.invoke(question)
print(f"{question}:\n{response.tool_calls}")





def validate_user(user_id: int, addresses: List) -> bool:
    """Validate user using historical addresses.

    Args:
        user_id: (int) the user ID.
        addresses: Previous addresses.
    """
    return True

model_chat = model_chat.bind_tools([validate_user])
question = "Could you validate user 123? They previously lived at 123 Fake St in Boston MA and 234 Pretend Boulevard in Houston TX."
response = model_chat.invoke(question)

response = model_chat.invoke(question)
print(f"{question}:\n{response.tool_calls}")
