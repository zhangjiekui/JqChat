
from openai import OpenAI
model_name = "/data/xinference/cache/mistral-large-instruct-gptq-123b"
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="abc123",
)

completion = client.chat.completions.create(
  model=model_name,
  messages=[
    {"role": "user", "content": "Hello!"}
  ]
)

print(completion.choices[0].message)


from langchain_core.tools import tool
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()
from langchain.tools.render import render_text_description # to describe tools as a string 
from jqcode.jq_agent.c0_init_env_models import env_models_instance

@tool
def accept(reason) -> int:
    "Accept a reason and return 1."
    logger.info(f"Accepting reason: {reason}")
    return 1


@tool
def reject(reason) -> int:
    "Reject a reason and return 0."
    logger.info(f"Rejecting reason: {reason}")
    return 0

tools = [accept,reject]
toos_dict = {tool.name:tool for tool in tools}
rendered_tools = render_text_description(tools)
# llm = env_models_instance.get_ollama_chat_model(tools=tools)
llm = env_models_instance.get_langchain_chat_model().bind_tools(tools)
print("==========="*10)
system_prompt = f"""You are an assistant that has access to functions.
    ONLY Use them:

    {rendered_tools}


    Given the user input, return the name and input of the tool to use.
    Return your response as a JSON blob with 'name' and 'arguments' keys.
    The value associated with the 'arguments' key should be a dictionary of parameters."""
print("==========="*10)


def LLM(prompt, system_message, model=llm):
    try:
        messages=[{"role": "system", "content": system_message}, {"role": "user", "content": prompt}]
        response = model.invoke(messages)
        print('Success:\n', response)

        if response.tool_calls:
            for tool in response.tool_calls:
                tool_name = tool['name']
                tool_args = tool['args']['reason']
                res = toos_dict[tool_name](tool_args)
                print(f"Result:调用了工具:{tool_name}，调用参数为:{tool_args},运行结果为:{res}")
                return res
    except Exception as error:
        print('Error:', error)
        raise
prompt = '使用python可以计算出3*10的正确结果，请思考这句话正确吗？并请给出理由'
res = LLM(prompt,system_prompt)
print(res)
