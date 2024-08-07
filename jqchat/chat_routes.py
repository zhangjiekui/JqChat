
import asyncio
from typing import List
from fastapi import APIRouter, Body, File, Request,Response, UploadFile

import os
from fastapi.responses import JSONResponse
import requests
import asyncio
import json
import re
import logging


import pandas as pd

from collections import deque


from jqchat.kernel_program.main import APP_PORT as KERNEL_APP_PORT
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_agent.graph_create_utils import user_question_is_related_to_coding_or_data_analyzing,llm
from jqcode.jq_agent.run_super_graph import super_graph_compiled_async,arun_super_graph
from jqcode.jq_agent.jq_rag_agent_sub_graph import llm_chain,invoke_llm_config
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage,SystemMessage
from langchain_ollama import ChatOllama


# HAS_DATA_FILE_UPLOADED = os.environ.get("HAS_DATA_FILE_UPLOADED", False)

#todo 保留openai只是暂时不想改代码
openai = env_models_instance.openai
# 官方推荐使用client = OpenAI()
openai_client = env_models_instance.openai_client


OPENAI_EXTRA_HEADERS = json.loads(os.environ.get("OPENAI_EXTRA_HEADERS", "{}"))

if openai.api_type == "open_ai":
    AVAILABLE_MODELS = json.loads(os.environ.get("OPENAI_MODELS", '''[{"displayName": "GPT-3.5", "name": "gpt-3.5-turbo"}, {"displayName": "GPT-4", "name": "gpt-4"}]'''))
elif openai.api_type == "azure":
    try:
        AVAILABLE_MODELS = json.loads(os.environ["AZURE_OPENAI_DEPLOYMENTS"])
    except KeyError as e:
        raise RuntimeError('AZURE_OPENAI_DEPLOYMENTS environment variable not set') from e
else:
    raise ValueError(f'Invalid OPENAI_API_TYPE: {openai.api_type}')

UPLOAD_FOLDER = 'workspace/'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
APP_PORT = int(os.environ.get("WEB_PORT", 8080))


class LimitedLengthString:
    def __init__(self, maxlen=2000):
        self.data = deque()
        self.len = 0
        self.maxlen = maxlen

    def append(self, string):
        self.data.append(string)
        self.len += len(string)
        while self.len > self.maxlen:
            popped = self.data.popleft()
            self.len -= len(popped)

    def get_string(self):
        result = ''.join(self.data)
        return result[-self.maxlen:]

class QuestionReWrite(BaseModel):
    """结合上下文context部分考虑重写原始问题，使得原始问题更加明确，仅仅需要返回问题本身，不要有任何额外的解释或内容：（1）如果原始问题中不明确的实体指代,如该公司，他，这个地方等，请重写原始问题，用明确的实体替换不明确的指代，但不要有任何的拓展；（2）否则，请直接返回原始问题本身。"""
    # k: str = Field(description="是否需要重写问题, k的值必须是'yes' or 'no'，'yes'表示需要重写")
    q: str = Field(description='返回格式必须为{"q":$question}:$question代表原始问题或重写后的问题内容，不要有任何额外的解释或内容')

question_rewrite_system_prompt = "结合上下文context部分考虑重写原始问题，使得原始问题更加明确，仅仅需要返回问题本身，不要有任何额外的解释或内容：（1）如果原始问题中不明确的实体指代,如该公司，他，这个地方等，请重写原始问题，用明确的实体替换不明确的指代，但不要有任何的拓展；（2）否则，请直接返回原始问题本身。"
question_rewrite_prompt = lambda x: ChatPromptTemplate.from_messages(
    [
        SystemMessage(question_rewrite_system_prompt),
        HumanMessage(
            f"'Context':\n{x['context']}\n'EndOfContext' \nQuestion: {x['question']} \nAnswer: "
        )
    ]
)
if isinstance(llm,ChatOllama):
    question_rewrite_llm = llm.with_structured_output(QuestionReWrite)
else:
    question_rewrite_llm = llm.with_structured_output(QuestionReWrite,method="function_calling")
question_rewrite_chain = question_rewrite_prompt | question_rewrite_llm

message_buffer = LimitedLengthString()
READER_MAP = {
    '.csv': pd.read_csv,
    '.tsv': pd.read_csv,
    '.xlsx': pd.read_excel,
    '.xls': pd.read_excel,
    '.xml': pd.read_xml,
    '.json': pd.read_json,
    '.hdf': pd.read_hdf,
    '.hdf5': pd.read_hdf,
    '.feather': pd.read_feather,
    '.parquet': pd.read_parquet,
    '.pkl': pd.read_pickle,
    '.sql': pd.read_sql,
}

def allowed_file(filename):
    _, ext = os.path.splitext(filename)
    if ext in READER_MAP.keys():
        return True
    else:
        return False


def inspect_file(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    try:
        df = READER_MAP[ext.lower()](filename)
        return f'The file contains the following columns: {", ".join(df.columns)}'
    except KeyError:
        return ''  # unsupported file type
    except Exception:
        return ''  # file reading failed. - Don't want to know why.

system_prompt=f"""请尽量使用中文来回答问题。Act as a data analyst hereby referred to as EXPERT with ten years of experience in the domain of data anylasis. Your role is to help inexperienced people explore/analyse data. Be sure to help the user understand what to focus on and give suggestions on where it would make sense to dig deeper.
    If generating Python code, follow the instructions under [GENERATE_PYTHON_INSTRUCTIONS].
        First, think step by step what you want to do and write it down in English.
        Then generate valid Python code in a code block 
        Make sure all code is valid - it will be run in a Jupyter Python 3 kernel environment. 
        MUST CHECK:
            Define every variable before you use it.
            Import every module/package before you use it.such as:
                import numpy as np
                import pandas as pd
                import seaborn as sns
                import matplotlib.pyplot as plt                
        Following modules/packages are available:
            For data munging, you can use 
                'numpy', # numpy==1.26.2
                'dateparser', # dateparser==1.2.0
                'pandas', # pandas==1.5.3
                'geopandas', # geopandas==0.14.1                
            For pdf extraction, you can use
                'PyPDF2', # PyPDF2==3.0.1
                'pdfminer', # pdfminer==20191125
                'pdfplumber', # pdfplumber==0.10.3
            For data visualization, you can use
                'matplotlib', # matplotlib==3.8.4
                'seaborn', # seaborn ==0.13.2
        Be sure to generate charts with matplotlib. If you need geographical charts, use geopandas with the geopandas.datasets module.
        If the user has just uploaded a file, focus on the file that was most recently uploaded (and optionally all previously uploaded files)
    
    Teacher mode: if the code modifies or produces a file, at the end of the code block insert a print statement that prints a link to it as HTML string: <a href='/download?file=INSERT_FILENAME_HERE'>Download file</a>. Replace INSERT_FILENAME_HERE with the actual filename.
    """

# todo:需同步更新readme中安装的软件包和这里的版本描述
usual_imports = """import numpy as np \nimport pandas as pd\nimport seaborn as sns\nimport matplotlib.pyplot as plt\n"""
async def get_code(user_prompt, user_openai_key=env_models_instance.api_key, model=env_models_instance.llm_model_name):

    user_code_prompt = f"""First, here is a history of what I asked you to do earlier. 
    The actual prompt follows after ENDOFHISTORY. 
    History:
    {message_buffer.get_string()}
    ENDOFHISTORY.
    Aiming to help the user in the best possible way with the below [USER_PROMPT] do one of the following:
    1. Write Python code, in a triple backtick Markdown code block, that supports what the user is trying to achieve. Use the instructions under [GENERATE_PYTHON_INSTRUCTIONS]
    2. Answer the question the user asks.
    3. Ask follow-up questions to better understand what the user wants to achieve. 
    
    [USER_PROMPT]
    {user_prompt}
    """

    if user_openai_key:
        openai.api_key = user_openai_key

    arguments = dict(
        temperature=0.1,
        # headers=OPENAI_EXTRA_HEADERS,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_code_prompt},
        ]
    )

    if openai.api_type == 'open_ai':
        arguments["model"] = model
    elif openai.api_type == 'azure':
        arguments["deployment_id"] = model
    else:
        return None, f"Error: Invalid OPENAI_PROVIDER: {openai.api_type}", 500

    try:
        result_GPT = openai_client.chat.completions.create(**arguments)
        # result_GPT = llm.invoke()

        if 'error' in result_GPT:
            raise openai.APIError(code=result_GPT.error.code, message=result_GPT.error.message)

        if result_GPT.choices[0].finish_reason == 'content_filter':
            raise openai.APIError('Content Filter')

    except openai.OpenAIError as e:
        return None, f"Error from API: {e}", 500

    try:
        content = result_GPT.choices[0].message.content

    except AttributeError:
        return None, f"Malformed answer from API: {content}", 500
    
    print('Will extract code from the content text:\n' + content)

    def extract_code(text):
        # Match triple backtick blocks first
        triple_match = re.search(r'```(?:\w+\n)?(.+?)```', text, re.DOTALL)
        if triple_match:
            return triple_match.group(1).strip()
        else:
            # If no triple backtick blocks, match single backtick blocks
            single_match = re.search(r'`(.+?)`', text, re.DOTALL)
            if single_match:
                return single_match.group(1).strip()
    text = content.strip()
    code = extract_code(text)
    # if code:
    #     code = usual_imports + code
    # else:
    #     code = "print('未生成code')"
    return code, text , 200


async def get_chat(user_prompt, user_openai_key=env_models_instance.api_key, model=env_models_instance.llm_model_name):

    user_chat_prompt = f"""First, here is a history of what I asked you to do earlier. 
    The actual prompt follows after ENDOFHISTORY. 
    History:
    {message_buffer.get_string()}
    ENDOFHISTORY.
    {user_prompt}
    DO NOT GENERATE ANY CODE
    Teacher mode: if the results return a link to a file that was generated, make sure to include the link in your answer.
    """

    # print('user_chat_prompt:\n' + user_chat_prompt)

    if user_openai_key:
        openai.api_key = user_openai_key

    arguments = dict(
        temperature=0.1,
        # headers=OPENAI_EXTRA_HEADERS,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_chat_prompt},
        ]
    )

    if openai.api_type == 'open_ai':
        arguments["model"] = model
    elif openai.api_type == 'azure':
        arguments["deployment_id"] = model
    else:
        return None, f"Error: Invalid OPENAI_PROVIDER: {openai.api_type}", 500

    try:
        # result_GPT = openai.ChatCompletion.create(**arguments)
        result_GPT =openai_client.chat.completions.create(**arguments)

        if 'error' in result_GPT:
            raise openai.APIError(code=result_GPT.error.code, message=result_GPT.error.message)

        if result_GPT.choices[0].finish_reason == 'content_filter':
            raise openai.APIError('Content Filter')

    except openai.OpenAIError as e:
        return None, f"Error from API: {e}", 500

    try:
        content = result_GPT.choices[0].message.content

    except AttributeError:
        return None, f"Malformed answer from API: {content}", 500
    
    return content, "Success", 200

# We know this Flask app is for local use. So we can disable the verbose Werkzeug logger
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

chat_router = APIRouter(prefix="/chat", tags=["Chat对话"])




@chat_router.api_route('/api/<path:path>', methods=["GET", "POST"])
def proxy_kernel_manager(path,request:Request):
    if request.method == "POST":
        print('starting code execution')
        requestjson = request.get_json()
        code = requestjson.get('command',None)
        if code:
            code = usual_imports + code
            requestjson = {'command': code}
            print('在代码实际执行之前,增加导入常用的程序包，如numpy，pandas，seaborn，matplotlib.pyplot等')
        else:
            code = print('未生成实际代码')
            requestjson = {'command': code}

        print(f"""started code execution with code:""")
        print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
        print(code)
        print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
        resp = requests.post(f'http://localhost:{KERNEL_APP_PORT}/{path}', json=requestjson)        
        # print(f"""started code execution with status: {resp.status_code} """)
        
    else:
        resp = requests.get(f'http://localhost:{KERNEL_APP_PORT}/{path}')

    excluded_headers = ['content-encoding',
                        'content-length', 'transfer-encoding', 'connection']
    headers = [(name, value) for (name, value) in resp.raw.headers.items()
               if name.lower() not in excluded_headers]

    response = Response(resp.content, resp.status_code, headers)
    return response



@chat_router.post('/inject-context')
def inject_context(
    user_prompt: str = Body(alias="prompt",description="用户输入"),
    ):
    # Append all messages to the message buffer for later use
    message_buffer.append(user_prompt + "\n\n")
    return JSONResponse(content={"result": "success"})



@chat_router.post('/completions',summary="对话接口")
# def generate_code():
def agent_entry(
    user_prompt: str = Body(alias="query",description="用户输入"),
    doc_id: str = Body(alias="doc", description="知识库ID"),
    user_id: str = Body(alias="user", description="用户随机ID"),
    ):
    print('============================================================')
    print('============================================================')
    print('触发python_backend......jqchat/webapp/main.py#L335')
    print('=='*30)
    print(f'(IN Web) User Question: {user_prompt}')
    model = env_models_instance.llm_model_name
    user_openai_key = env_models_instance.api_key
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    code, text, status = None, None, 200
    config = {"recursion_limit":25,"configurable": {"thread_id": user_id}}
    initial_graph_state = asyncio.run(super_graph_compiled_async.aget_state(config=config)).values
    messages = initial_graph_state.get('messages',[])
    
    n_last_messages_num = 3
    if len(messages)>n_last_messages_num:
        n_last_messages = messages[-n_last_messages_num:]
    else:
        n_last_messages = messages

    print(f"进入改写环节前的user_prompt={user_prompt}")
    original_question = user_prompt
    if n_last_messages:
        history_messages_contents = [m.content for m in n_last_messages]
        history_messages_context = '||'.join(history_messages_contents)
        rewrited_question = ''
        try:
            result = question_rewrite_chain.invoke({"question": f"用户原始问题为：“{user_prompt}”","context":history_messages_context},config=invoke_llm_config)
            print(f'question_rewrite_chain {result=}')
            rewrited_question = result.q

        except Exception as e:
            print(f"question_rewrite_chain执行出现错误:{e},但忽略")
            # prompt = "请结合下面的context部分考虑重写原始问题，使得原始问题更加明确，仅仅需要返回问题本身，不要有任何额外的解释或内容：（1）如果原始问题中不明确的实体指代,如该公司，他，这个地方等，请重写原始问题，用明确的实体替换不明确的指代，但不要有任何的拓展；（2）否则，请直接返回原始问题本身。"
            # rewrited_question = llm_chain.invoke({"question": f"用户原始问题为：“{user_prompt}”\n{prompt}","context":history_messages_context},config=invoke_llm_config)
        print(f"改写后得到的rewrited_question={rewrited_question}")
        if rewrited_question:
            user_prompt = rewrited_question   

        print(f"original_question={original_question}")
        print(f'history_messages_context={history_messages_context}')
        print(f"rewrited_question={user_prompt}")

    rewrited_feedback = ""
    if user_prompt != original_question:
        rewrited_feedback = f'【提示：对您的原始问题进行了改写：{original_question}  ==》 {user_prompt}】\n\n'

    is_coding_related = user_question_is_related_to_coding_or_data_analyzing(question=user_prompt)
    
    HAS_DATA_FILE_UPLOADED = os.environ.get("HAS_DATA_FILE_UPLOADED", False)
    if HAS_DATA_FILE_UPLOADED and is_coding_related:
        code, text, status = loop.run_until_complete(get_code(user_prompt, user_openai_key, model))
    else:
        text, with_exception = arun_super_graph(question=user_prompt,config=config,super_graph_compiled_async=super_graph_compiled_async)
        if with_exception:
            if is_coding_related:
                print('前面程序运行或判断出现了问题，下面试图使用Python代码方式来解决......')
                code, text, status = loop.run_until_complete(get_code(user_prompt, user_openai_key, model))

    print('~~'*30)
    if code:
        print('生成的Python代码为:')
        print(code)
    loop.close()
    print('~~'*30)
    print('=='*30)
    # Append all messages to the message buffer for later use
    message_buffer.append(user_prompt + "\n\n")

    if rewrited_feedback:
        text = rewrited_feedback + text

    return JSONResponse(content={"code":code,"text":text},status_code=status)

@chat_router.post('/chat',summary="纯聊天接口")
def generate_chat(
    model:str,
    user:str,
    doc:str,
    openAIKey:str,
    prompt:str,
    request:Request):
    #all of this comes from the system, not the user!
    if(model is None ):
        model=(env_models_instance.llm_model_name)
    print('CHAT_TEXT: ' + prompt)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    text, exeption_message, status = loop.run_until_complete(
        #TODO:需要此处增加传入的user_id和doc_id
        get_chat(prompt, openAIKey, model))
    loop.close()
    if text is None:
        print(exeption_message)
        text = exeption_message


    # Append all messages to the message buffer for later use
    prompt = 'USER: ' + prompt + "\n\n"
    message_buffer.append(prompt)
    # print(f"""RETURNING TO UI: ${status}""")
    return JSONResponse(content={'text': text}, status_code=status)
    # return jsonify({'text': user_prompt + text}), status

@chat_router.post('/upload',summary="上传接口")
def upload_file(
    file: UploadFile = File(..., description="上传文件"),
    ):
    # check if the post request has the file part
    # if 'file' not in request.files:
    #     return ({'error': 'No file part in the request'}), 400
    # file = request.files['file']
    # if user does not select file, browser also
    # submit an empty part without filename
    if file.filename == '':
        return ({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        file_target = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_target)
        file_info = inspect_file(file_target)
        os.environ["HAS_DATA_FILE_UPLOADED"] = 'True'
        message_buffer.append(f"已上传保存的文件名为{file.filename},请在分析过程中使用这个数据文件" + "\n\n")
        return JSONResponse(content={'message': f'File {file.filename} uploaded successfully.\n{file_info}'}, status_code=200)
    else:
        return JSONResponse(content={'error': 'File type not allowed'}, status_code=400)
