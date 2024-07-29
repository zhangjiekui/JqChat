from langchain_core.messages import HumanMessage
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from typing import List

llm_ollama_chat = env_models_instance.get_ollama_chat_model(model_name = "llama3-groq-tool-use:8b-q8_0")


def create_route(members):
    system_prompt = f"""
        Given the user questions, dicide next action should take:{members}
        Action 'Tools' Only responsible for tool calls, such as query flight numbers and generate/run python code,
        while action 'Rag' responsible for all other things, such as daily greetings and chatting, search web or knowledge base/vectorstore to answer user's question.
        When finished, respond with action 'FINISH'.
                
        Args:
            next: (str) next action should take.
        """  
    
    def route(next:str) -> bool:
        return True

    route.__doc__ = system_prompt
    return route

route = create_route(members=["Tools", "Rag", "FINISH" ])

model_chat = env_models_instance.get_ollama_chat_model(model_name = "llama3-groq-tool-use:8b-q8_0")
model_chat = model_chat.bind_tools([route])
response = model_chat.invoke("请调用工具查询查询明天从合肥到上海的航班")

print(response.tool_calls)

response = model_chat.invoke("what is the weather in Singapore?")

print(response.tool_calls)

# https://python.langchain.com/v0.2/docs/integrations/chat/ollama/
# https://github.com/langchain-ai/langchain/blob/master/docs/docs/integrations/chat/ollama.ipynb

def validate_user(user_id: int, addresses: List) -> bool:
    """Validate user using historical addresses.

    Args:
        user_id: (int) the user ID.
        addresses: Previous addresses.
    """
    return True

model_chat = model_chat.bind_tools([validate_user])
response = model_chat.invoke("Could you validate user 123? They previously lived at "
    "123 Fake St in Boston MA and 234 Pretend Boulevard in "
    "Houston TX.")

print(response.tool_calls)