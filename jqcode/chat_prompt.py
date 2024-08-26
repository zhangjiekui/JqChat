



import os
import json
import re
import pandas as pd
from collections import deque


# HAS_DATA_FILE_UPLOADED = os.environ.get("HAS_DATA_FILE_UPLOADED", False)


UPLOAD_FOLDER = 'workspace/'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
APP_PORT = int(os.environ.get("WEB_PORT", 8080))

READER_MAP = {
    '.csv': pd.read_csv,
    '.xlsx': pd.read_excel,
    '.xls': pd.read_excel,
    '.docx':pd.read_hdf,
    '.doc':pd.read_hdf,
    '.pdf':pd.read_hdf
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


# async def get_chat(user_prompt, user_openai_key=env_models_instance.api_key, model=env_models_instance.llm_model_name):

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
