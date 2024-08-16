# The GPT web UI as a template based Flask app
import os, sys,pathlib    
# 添加这行代码

def add_import_paths():
    project_root_path = pathlib.Path().resolve()
    p1 = project_root_path/'jqcode'
    p2 = project_root_path/'jqchatweb'

    added_paths = [project_root_path, p1, p2]
    for p in added_paths:
        sys.path.append(p)
    return added_paths
added_paths = add_import_paths()

import os


import requests
import asyncio
import json
import re
import logging
import sys

import pandas as pd

from collections import deque

from flask_cors import CORS
from flask import Flask, request, jsonify, send_from_directory, Response
try:
    from jqchatweb.kernel_program.main import APP_PORT as KERNEL_APP_PORT
except:
    from kernel_program.main import APP_PORT as KERNEL_APP_PORT
    from jqchatweb.kernel_program.main import APP_PORT
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_agent.graph_create_utils import user_question_is_related_to_coding_or_data_analyzing,llm

from langgraph_in_class import GraphAgent,invoke_llm_config,message_buffer,question_rewrite_chain

from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage,SystemMessage,ToolMessage,AIMessage
from langchain_ollama import ChatOllama
# region 打算删除的代码
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
# endregion



UPLOAD_FOLDER = 'workspace/'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
APP_PORT = int(os.environ.get("WEB_PORT", 8080))



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
    only_filename = os.path.basename(filename)
    try:
        df = READER_MAP[ext.lower()](filename)
        return f'文件“{only_filename}”包含以下列名: {", ".join(df.columns)}'
    except KeyError:
        return ''  # unsupported file type
    except Exception:
        return ''  # file reading failed. - Don't want to know why.
    
file_info = inspect_file('/data/projects/JqChat/workspace/0研发工单统计.xls')  
print(file_info)  

system_prompt=f"""请尽量使用简体中文来解答用户问题。
    Act as an EXPERT with ten years of experience in the domain of data anylasis, your role is to help inexperienced people explore/analyse data. 
    Be sure to help the user understand what to focus on and give suggestions on where it would make sense to dig deeper.
    If you need to use/generate Python code, follow the instructions under [GENERATE_PYTHON_INSTRUCTIONS].
    GENERATE_PYTHON_INSTRUCTIONS:
        First, think step by step what you want to do and write it down in Simplified Chinese.
        Then generate valid Python code all in a code block 
        Make sure all code is valid - it will be run in a Jupyter Python 3 kernel environment. 
        MUST CHECK:
            Define every variable before you use it.
            Import every module/package before you use it.such as:
                import numpy as np
                import pandas as pd
                import seaborn as sns
                import matplotlib.pyplot as plt
                import plotly.express as px
                import plotly.graph_objects as go                
        Following modules/packages are available:
            For data wrangling/munging, you can use 
                'numpy',
                'dateparser',
                'pandas',
            For data visualization, you can use
                'matplotlib',
                'seaborn',
                'plotly',
        Be sure to generate charts with plotly/matplotlib/seaborn, plotly is preferred. But if you need geographical charts, use geopandas with the geopandas.datasets module.
        If the user has just uploaded a file, focus on the file that was most recently uploaded (and optionally all previously uploaded files)
    
        If the code modifies or produces a file/image, please add a print statement at the end of the code block that prints a link to it as HTML string: <a href='/download?file=INSERT_FILENAME_HERE'>Download file</a>. Replace INSERT_FILENAME_HERE with the actual filename.
    EndOf_GENERATE_PYTHON_INSTRUCTIONS
    """

# todo:需同步更新readme中安装的软件包和这里的版本描述
usual_imports = """import numpy as np \nimport pandas as pd\nimport seaborn as sns\nimport matplotlib.pyplot as plt\nimport plotly.express as px\nimport plotly.graph_objects as go"""
async def get_code(user_prompt, user_openai_key=env_models_instance.api_key, model=env_models_instance.llm_model_name):

    user_code_prompt = f"""First, here is a history of what I asked you to do earlier. 
    The actual prompt follows after ENDOFHISTORY. 
    History:
    {message_buffer.get_string()}
    ENDOFHISTORY.
    Aiming to help the user in the best possible way with the below [USER_PROMPT] do one of the following:
    1. Write Python code, in a triple backtick Markdown code block, that supports what the user is trying to achieve. Follows the instructions under [GENERATE_PYTHON_INSTRUCTIONS]
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
    If the results return a link to a file/image that was generated, make sure to include the link in your answer.
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

cli = sys.modules['flask.cli']
cli.show_server_banner = lambda *x: None

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

CORS(app)


@app.route('/')
def index():

    # Check if index.html exists in the static folder
    if not os.path.exists(os.path.join(app.root_path, 'static/index.html')):
        print("index.html not found in static folder. Exiting. Did you forget to run `make compile_frontend` before installing the local package?")

    return send_from_directory('static', 'index.html')


@app.route("/models")
def models():
    return jsonify(AVAILABLE_MODELS)

#获取知识库列表
@app.route("/docs")
def docs():
    return  jsonify(env_models_instance.get_all_knowledge_base(None,True))




@app.route('/api/<path:path>', methods=["GET", "POST"])
def proxy_kernel_manager(path):
    if request.method == "POST":
        print('starting code execution')
        requestjson = request.get_json()
        code = requestjson.get('command',None)
        if not code:
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


@app.route('/assets/<path:path>')
def serve_static(path):
    return send_from_directory('static/assets/', path)


@app.route('/download')
def download_file():

    # Get query argument file
    file = request.args.get('file')
    # from `workspace/` send the file
    # make sure to set required headers to make it download the file
    return send_from_directory(os.path.join(os.getcwd(), 'workspace'), file, as_attachment=True)


@app.route('/inject-context', methods=['POST'])
def inject_context():
    user_prompt = request.json.get('prompt', '')

    # Append all messages to the message buffer for later use
    message_buffer.append(user_prompt + "\n\n")

    return jsonify({"result": "success"})



@app.route('/generate', methods=['POST'])
# def generate_code():
def agent_entry():
    print('============================================================')
    print('============================================================')
    print('触发python_backend......jqchat/webapp/main.py#L335')
    user_prompt = request.json.get('prompt', '')
    #获取用户随机ID
    user_id=request.json.get('user',None)
    #获得知识库的字典{"name": "test" , "discription":"测试方面的知识库",...}
    kb_base_dict=request.json.get('doc','es_test')
    allow_question_rewrite = request.json.get('allow_question_rewrite',True)


    print(f"{user_id=}")

    # user_id = 'fixed_user'
    chat_bot = GraphAgent(memory_thread_id=user_id, kb_base_dict=kb_base_dict)
    print(f"{chat_bot.user_id=}")
    # 由于问题改写在少数情况下可能不是用户想要的，所以应允许用户关闭
    text = chat_bot.run_conversation(user_question=user_prompt,allow_question_rewrite=allow_question_rewrite)
    code = ''
    messages = chat_bot.get_all_history_messages()
    last_message = messages[-1]
    if isinstance(last_message,ToolMessage):
        if last_message.name == 'CODE_EXECUTION':
            kwargs = last_message.additional_kwargs
            question_id = kwargs.get("question_id")
            if question_id == chat_bot.question_id:
                code_text = kwargs.get("code_text","")
                code = kwargs.get("code","")
                if code_text:
                    text = code_text + '\n' + text

 
    return jsonify({'code':code,'text': text}), 200


@app.route('/chat', methods=['POST'])
def generate_chat(model=env_models_instance.llm_model_name):
    #all of this comes from the system, not the user!
    user_prompt = request.json.get('prompt', '')
    user_openai_key = request.json.get('openAIKey', None)
    # model = request.json.get('model', None)
    #获取用户随机ID
    user_id=request.json.get('user',None)
    #获得文档ID
    doc_id=request.json.get('doc',None);

    print('CHAT_TEXT: ' + user_prompt)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    text, exeption_message, status = loop.run_until_complete(
        #TODO:需要此处增加传入的user_id和doc_id
        get_chat(user_prompt, user_openai_key, model))
    loop.close()
    if text is None:
        print(exeption_message)
        text = exeption_message


    # Append all messages to the message buffer for later use
    user_prompt = 'USER: ' + user_prompt + "\n\n"
    message_buffer.append(user_prompt)
    # print(f"""RETURNING TO UI: ${status}""")
    return jsonify({'text': text}), status
    # return jsonify({'text': user_prompt + text}), status

@app.route('/upload', methods=['POST'])
def upload_file():
    # check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    file = request.files['file']
    # if user does not select file, browser also
    # submit an empty part without filename
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        file_target = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_target)
        file_info = inspect_file(file_target)
        os.environ["HAS_DATA_FILE_UPLOADED"] = 'True'
        message_buffer.append(f"已上传保存的文件名为{file.filename},请在分析过程中使用这个数据文件" + "\n\n")
        return jsonify({'message': f'File {file.filename} uploaded successfully.\n{file_info}'}), 200
    else:
        return jsonify({'error': 'File type not allowed'}), 400

def test():
    print(allowed_file('a.csv'))
    print(allowed_file('a.xx'))

if __name__ == '__main__':
    # test()
    app.run(host="0.0.0.0", port=APP_PORT, debug=True, use_reloader=False)

    # litellm ollama proxy https://github.com/BerriAI/litellm/blob/5583197d635158bbe9be41b5ca797a975ef3c905/docs/my-website/docs/tutorials/model_config_proxy.md
    # litellm --model ollama_chat/wizardlm2:8x22b-q2_K https://microsoft.github.io/autogen/docs/topics/non-openai-models/local-litellm-ollama/
    # https://github.com/ollama/ollama/blob/main/docs/gpu.md
    # ollama run wizardlm2:8x22b-q2_K


    # litellm --model ollama_chat/wizardlm2:8x22b-q2_K  --api_base https://my-endpoint.com
    #  Uvicorn running on http://0.0.0.0:4000
    # "model": "NotRequired", # Loaded with LiteLLM command
    # "api_key": "NotRequired", # Not needed
    # "base_url": "http://0.0.0.0:4000"  # Your LiteLLM URL
    # 配置https://github.com/ollama/ollama/blob/main/docs/faq.md#how-do-i-configure-ollama-server