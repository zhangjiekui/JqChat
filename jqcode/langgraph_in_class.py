# source: https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components
# print('参考：https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components')
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Union, List
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage,SystemMessage, HumanMessage,ToolMessage,AIMessage
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_openai import ChatOpenAI
from langchain.schema import Document
from langchain_core.output_parsers import StrOutputParser
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from jqcode.jq_agent.c0_init_env_models import env_models_instance,clean_up_list_when_encounter_null_element
from jqcode.jq_agent.tools.jq_functions_and_tools import get_flight_number,python_repl_tool,get_elderly_organization_list
from jqcode.jq_agent.tools.jq_retriever import get_retriever
import asyncio
from langchain_community.tools import TavilySearchResults
from langchain_core.tools import Tool
from langgraph.prebuilt import create_react_agent
from jqcode.jq_agent.tools.jq_web_search_engine import get_web_search_documents as search
from jqcode.jq_agent.tools.jq_web_search_engine_async import get_web_search_documents as async_search
import os
import re
import shutil
from base64 import b64decode
from pathlib import Path
from jqcode.jq_code_executor.code_executor import CodeExecutorTool
from jqcode.jq_code_executor.code_executor_in_aio_sandbox import code_executor_in_sandbox
import json_repair
import shortuuid
import uuid
from jqcode.jq_utils.logger import jqkj_logger
from dotenv import load_dotenv
from datetime import datetime
from jqcode.jq_queue.jq_queues import JqFileSystemQueue

if not os.environ["env_loaded"]:
    _ = load_dotenv()
logger = jqkj_logger(__file__).get_logger()
# python_repl = PythonREPLTool().run #这是原生的
# python_repl = python_repl_tool #这是我自己定义的，强制加入了print,已获取输出值
# python_repl = eval  
# llm_model = env_models_instance.openai_chat_model or env_models_instance.chat_model
llm_model = env_models_instance.chat_model
# DEBUG_LLM_USING_CUSTOM_HANDLER
invoke_llm_config = env_models_instance.invoke_llm_config 


class GraphAgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    question : str
    question_related_messages: Annotated[list[BaseMessage], clean_up_list_when_encounter_null_element]
    # retrieval_history : dict
    question_searched : dict
    generation : str
    documents : List[str]
    # 存放用户相关的临时/中间变量，取代之前使用的系统环境变量方式，如：os.environ['rag_args']、os.environ["REFERENCE"]
    # {"$user_id":{"rag_args":"$rag_args","reference":"$reference"}}
    user_variables:dict 

# region: LimitedLengthString
# class LimitedLengthString:
#     def __init__(self, maxlen=8000):
#         self.data = deque()
#         self.len = 0
#         self.maxlen = maxlen
#     def append(self, contents:Union[str,List[str],List[BaseMessage]]):
#         if not isinstance(contents,list):
#             contents = [contents]
#         for content in contents:
#             content = content.content if isinstance(content,BaseMessage) else content
#             content = content.strip()
#             if content:
#                 if content not in self.data:
#                     self.data.append(content)
#                     self.len += len(content)
#                     while self.len > self.maxlen:
#                         popped = self.data.popleft()
#                         self.len -= len(popped)
#                 else:
#                     logger.info(f"LimitedLengthString中已经存在'{content}'，忽略此次操作")        

#     def get_string(self):
#         result = '\n'.join(self.data)
#         return result[-self.maxlen:]    
# message_buffer = LimitedLengthString()
# endregion: LimitedLengthString

# region
### Data model and Chains Definitions

# question_rewrite_system_prompt = """你是一位擅长根据上下文'Context'，对原始问题('Query'后面的内容)进行优化重写的专家。目标是使得原始问题更加明确具体，但又绝不能改变原始问题的本来意思或意图，所以请秉持谨慎、忠实的态度，具体方法建议仅使用实体消歧(Disambiguation)、指代消解(Co-reference Resolution)等技术。
#     如果不确信需要进行优化重写，请直接返回原始问题本身。
#     仅仅需要返回问题内容本身，绝不能有任何额外的解释或内容。
#     返回格式必须为Json:{"q":$Query}，请使用改写后的问题内容替换$Query
#     """


# question_rewrite_system_prompt = """
# 请根据当前对话的上下文'Context'，对用户的最新问题（'Query'后面的内容）进行重写，使其满足以下要求：
# 1. ==&zwnj;**上下文融合**&zwnj;==：补充用户省略的、但上文已提及的关键信息（如时间、地点、人物、对象属性等）；
# 2. ==&zwnj;**意图保留**&zwnj;==：确保重写后的问题与原意完全一致，不扭曲用户目的；
# 3. ==&zwnj;**清晰简洁**&zwnj;==：用完整、明确的自然语言表达，避免歧义；
# 4. ==&zwnj;**无需扩展**&zwnj;==：仅整合已有上下文信息，不添加假设性内容。

# ==&zwnj;**示例**&zwnj;==：
# - 上文：用户：“我想订购iPhone 15 Pro Max，星空黑有货吗？”
# - 当前问题：用户：“到了吗？”
# - 重写后：“我上周订购的iPhone 15 Pro Max星空黑版本现在到货了吗？”

# ==&zwnj;**示例**&zwnj;==：
# - 上文：用户：“我叫张三”
# - 当前问题：用户：“请搜索我与**公司的关系”
# - 重写后：“请搜索张三与**公司的关系”

# ==&zwnj;**输出要求**&zwnj;==：
# - 仅输出重写后的问题，无需解释；
# - 若上下文无关或信息不足，直接返回原问题。
# - 返回格式必须为Json:{"q":$Query}，请使用改写后的问题内容替换$Query

# """
# endregion
question_rewrite_system_prompt = """
【‌任务说明‌】
请根据上下文'Context'，重写用户问题（'Query'后面的内容），‌将模糊的代词（如“我”、“他”、“那里”等）替换为上下文中已明确的具体信息‌（如姓名、地点、时间、机构等），使问题独立且清晰，无需依赖额外上下文即可理解。注意：上下文中内容或问题都是已经解决了的，所以不要再用来扩充当前用户问题，确保重写后的问题与当前用户问题原意完全一致，不添加或删减信息。

【‌输出规则‌】
‌识别实体‌：从历史会话中提取关键实体（如人名“张三”、地点“北京”、时间“明天”）。
‌替换指代‌：将代词替换为对应实体，优先使用最相关且最近提及的信息。替换时注意分辨你自己和用户的信息，你们都可能自称为‘我’，不要搞混淆了。
‌保持原意‌：确保重写后的问题与原意完全一致，不添加或删减信息，不要扩充。
输出要求：仅输出重写后的问题，无需解释；若上下文无关或信息不足，直接返回原问题；返回格式必须为Json:{"q":$Query}，请使用改写后的问题内容替换$Query
"""

question_rewrite_prompt = lambda x: ChatPromptTemplate.from_messages(
    [
        SystemMessage(question_rewrite_system_prompt),
        HumanMessage(
            f"'Context':\n{x['context']}\n'EndOfContext' \n'Query': {x['question']} \nAnswer: "
        )
    ]
)
# messages = question_rewrite_prompt({'context':"历史消息内容",'question':'请绘制sin(x)曲线图'}).format_messages()
question_rewrite_chain = question_rewrite_prompt | llm_model

class WEB_SEARCH(BaseModel):
    """
    网络搜索工具。 使用网络网络搜索工具从网络上获取相关信息以回答用户问题, 特别是2024年及以后的信息，尤其是用户问题中提及了“使用网络搜索”的时候，请优先调用网络搜索工具(WEB_SEARCH).
    """
    query: str = Field(description="The query to use when searching the internet.")

prompt_llm = """You are an assistant for question-answering tasks. Answer the question based upon your knowledge in the language the user asked, preferred/default to Simplified Chinese."""
# Prompt
prompt = lambda x: ChatPromptTemplate.from_messages(
    [
        SystemMessage(prompt_llm),
        HumanMessage(
            f"'Context':\n{x['context']}\n'EndOfContext' \nQuestion: {x['question']} \nAnswer: "
        )
    ]
)
# LLM Chain for query regenerating
llm_chain = prompt | llm_model | StrOutputParser()




class CODE_GENERATION(BaseModel,extra='allow'):
    """
    Code Assistant/Code generation . Use programming code (preferred Python language) to slove a user question, if the question related to [code generating, file processing/analyzing, data exploring/analyzing/visualizing].
    """
    query: str = Field(description="The query to use when need to generate python code.")

class CODE_EXECUTION(BaseModel,extra='allow'):
    """
    Code execution/Code intepreter. When user providing a code snippet and asking for running/executing, w or w/o returning the result.
    """
    query: str = Field(description="The query to use when asking for running/executing a code snippet.")
### End: Router Data model Class Definitions
# endregion


# region: Some utils mothods or varaiables


usual_imports = """import numpy as np\nimport pandas as pd\nimport seaborn as sns\nimport matplotlib.pyplot as plt\nimport plotly.express as px\nimport plotly.graph_objects as go"""

usual_imports_list = usual_imports.split("\n")
usual_imports_list_striped = [line.strip() for line in usual_imports_list]
def merge_code_with_usual_imports(code:str,usual_imports_list=usual_imports_list_striped):
    code_lines = code.split("\n")
    code_lines_striped = [line.rstrip() for line in code_lines]

    code_lines_is_import = [code_line for code_line in code_lines_striped if code_line.lstrip().startswith('import')] 
   
    for code_line in usual_imports_list:
        if code_line not in code_lines_is_import:
            code_lines_striped.insert(1,code_line)
        else:
            if 'import matplotlib.pyplot' in code_line:
                code_lines_striped.remove(code_line)
                new_code_line = "import matplotlib.pyplot as plt\n"
                if 'font.sans-serif' not in code:
                    new_code_line += "plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'SimHei', 'Microsoft YaHei', 'DejaVu Sans']\n"
                if 'axes.unicode_minus' not in code:
                    new_code_line += "plt.rcParams['axes.unicode_minus'] = False\n"
                code_lines_striped.insert(0,new_code_line)
    code = "\n".join(code_lines_striped)
    return code

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
        else:
            return text

def display_code(code:str):
    _code = f"""\n```python\n{code}\n```"""
    return _code

def display_text(text:str):
    _text = text.lower()
    if '\nfinal answer:' in _text and '\naction:' in _text:
        _index0 = _text.rindex('\nfinal answer:')
        _l = len('\nfinal answer:')
        idx = _index0 + _l
        _index1 = _text.rindex('\naction:')
        text = text[idx:_index1].replace('\nFinal Answer:','')
    elif '\nfinal answer:' in _text:
        _index0 = _text.rindex('\nfinal answer:')
        _l = len('\nfinal answer:')
        idx = _index0 + _l
        text = text[idx:].replace('\nFinal Answer:','')
    return text

# text="""I now know the final answer.
# Final answer: 已经成功绘制了cos(x)曲线图。从图中可以看出，cos(x)曲线在x=0时开始"""
# print(display_text(text))
# pass

# endregion: Some utils mothods or varaiables

    

# region: Rags Related
    
# 1. Coding Relavance Grader
class GradeCodingRelavance(BaseModel,extra='allow'):
    """Binary classification for a user question is relevant to [code generating/executing,file processing/analyzing, data exploring/analyzing]."""
    k: str = Field(description="Whether a user question is relevant to [code generating/executing,file processing/analyzing, data exploring/analyzing], k must be 'yes' or 'no'")

prompt_coding_relevant_grader = """You are a grader assessing relevance of a user question to [code generating/executing,file processing/analyzing, data exploring/analyzing]. Response me with a simple JSON string can be directly consumed by  ‘json.loads’ method, must be ‘{{"k":"yes"}}’ or  ‘{{"k":"no"}}’,'yes' means a user question is related to Python code generating/code executing.No preamble or explaination."""
if env_models_instance.need_json_mode:
    structured_llm_coding_relevant_grader = llm_model.with_structured_output(GradeCodingRelavance,method='json_mode')
else:
    structured_llm_coding_relevant_grader = llm_model.with_structured_output(GradeCodingRelavance)

coding_relevance_prompt = ChatPromptTemplate.from_messages(
    [
        ("system",prompt_coding_relevant_grader),
        # SystemMessage(prompt_coding_relevant_grader), #就可以在提示语中不必使用‘{{"k":"yes"}}’
        ("human", "User question: {question}")
    ]
)
coding_relevance_grader = coding_relevance_prompt | structured_llm_coding_relevant_grader


# 2. Retrieved Documents Relevance Grading
class GradeDocumentsRelavance(BaseModel,extra='allow'):
    """Binary classification for relevance check on retrieved documents."""
    k: str = Field(description="Whether Documents are relevant to the question, k must be 'yes' or 'no'")

prompt_documents_relevant_grader = """You are a grader assessing relevance of a retrieved document to a user question. If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant. It does not need to be a stringent test.The goal is to filter out erroneous retrievals. Response me with a simple JSON string can be directly consumed by  ‘json.loads’ method, must be ‘{{"k":"yes"}}’ or  ‘{{"k":"no"}}’,'yes' means a retrieved document is related to a user question.No preamble or explaination."""
if env_models_instance.need_json_mode:
    structured_llm_documents_relevant_grader = llm_model.with_structured_output(GradeDocumentsRelavance,method='json_mode')
else:
    structured_llm_documents_relevant_grader = llm_model.with_structured_output(GradeDocumentsRelavance)
retrieval_document_relevance_prompt = ChatPromptTemplate.from_messages(
    [
        ("system",prompt_documents_relevant_grader),
        # SystemMessage(prompt_coding_relevant_grader), #就可以在提示语中不必使用‘{{"k":"yes"}}’
        ("human", "Retrieved document: {document} \n\n User question: {question}")
    ]
)
retrieval_document_relevance_grader = retrieval_document_relevance_prompt | structured_llm_documents_relevant_grader

def grade_documents(state:GraphAgentState):
    """
    Determines whether the retrieved documents are relevant to the question.

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Updates documents key with only filtered relevant documents
    """

    print("---BYPASS CHECK DOCUMENT RELEVANCE TO QUESTION---")
    documents = state["documents"]
    return {"documents": documents,"user_variables":state["user_variables"]}
    # region
    # question = state["question"]
    # documents = state["documents"]
    
    # # Score each doc
    # filtered_docs = []
    # try:
    #     scores = retrieval_document_relevance_grader.batch([{"question": question, "document": d.page_content} for d in documents],config=invoke_llm_config)    
    #     for i,score in enumerate(scores):
    #         d = documents[i]  
    #         grade = score.k
    #         if grade == "yes":
    #             print("---GRADE: DOCUMENT RELEVANT---")
    #             filtered_docs.append(d)
    #         else:
    #             metadata=d.metadata
    #             relevance_score_retriever_embedding = metadata.get('relevance_score_retriever_embedding',0)
    #             relevance_score_retriever_bm25 = metadata.get('relevance_score_retriever_bm25',0)
    #             relevance_score_reranker = metadata.get('relevance_score_reranker',0)
    #             if relevance_score_retriever_embedding > 0.7 or relevance_score_reranker>0.5 or relevance_score_retriever_bm25 > 70:
    #                 filtered_docs.append(d)
    #                 print("---GRADE:LLM DOCUMENT NOT RELEVANT, BUT RETRIEVER 'relevance_score' IS HIGH---")
    #                 print("---GRADE:SO STILL THINK DOCUMENT RELEVANT")
    #             else:
    #                 print("---GRADE: DOCUMENT NOT RELEVANT---")

    # except Exception as e:
    #     print(f"---ERROR: 无法获取'retrieval_document_relevance_grader'的判别结果，详细错误信息如下:---")
    #     print(e)
    #     filtered_docs.append(d)
    # return {"documents": filtered_docs}
    # relevance_filtered_results = "\n".join([d.page_content for d in filtered_docs])
    # relevance_filtered_message = ToolMessage(content=relevance_filtered_results,name='grade_documents',tool_call_id='0')
    # return {"documents": filtered_docs, "question": question, "messages":relevance_filtered_message}
    # endregion

# 3. Decide to Generate if Retrieved Documents is Relevant Route to web_search
def decide_to_generate(state:GraphAgentState):
    """
    Determines whether to generate an answer, or re-generate a question.

    Args:
        state (dict): The current graph state

    Returns:
        str: Binary decision for next node to call
    """

    print("---DECIDED TO GENERATE OR WEB SEARCH BASED ON HAVINE ANY DOCUMENTS RELEVANT TO QUESTION ---")
    filtered_documents = state["documents"]

    if not filtered_documents:
        # All documents have been filtered check_relevance
        # We will re-generate a new query
        print("---DECISION: ALL DOCUMENTS ARE NOT RELEVANT TO QUESTION, WEB SEARCH---")
        return "web_search"
    else:
        # We have relevant documents, so generate answer
        print("---DECISION: GENERATE---")
        return "generate"

# 4. RAG Generation Chain
# prompt参考自： https://docs.anthropic.com/en/prompt-library/cite-your-sources
prompt_rag_part1 = "You are an assistant for question-answering tasks. Use the following retrieved documents to answer the question, each starting with a reference number like [x], where x is a number:"

prompt_rag_part2 = """
以下内容将以Markdown的方式来渲染呈现，请务必符合Markdown的语法规范，并尽量美观，去除无意义的字符

First, starting with "#### 引用片段:"  \n  , find the quotes from the documents that are most relevant to answering the question, and then print them in numbered order. Each quote should be a relatively short summary sentence of the quoted document, such as '<p class="referens_content">[1] Company X reported revenue of $12 million in 2021'. And print in a seperated paragraph,by adding "  \n  ". 

If there are no relevant quotes, write “没有发现相关的引用内容” instead.

Then, answer the question, starting with "#### 最终回答:"  \n  . Do include or reference quoted content verbatim in the answer if possible.But Don’t say “According to Quote [1]” when answering. Instead make references to quotes relevant to each section of the answer solely by adding their bracketed reference numbers at the end of relevant quotes, If a section of the answer comes from multiple quotes, please list all applicable citations, like <sup><font color="red">[1]</font></sup><sup><font color="red">[2]</font></sup>, and MUST place the citation(s) between text content punctuation marks, 例如：
正确格式为：'文字内容<sup><font color="red">[1]</font></sup>  。'
错误格式为：'文字内容。<sup><font color="red">[1]</font></sup>  ' 错误原因为：将引用'<sup><font color="red">[1]</font></sup>  '错误地放到了标点符号'。'之前

Thus, the format of your overall response should look like what’s shown between the tags. Make sure to strictly follow the formatting (such as <p class="referens_content">...</p>,'...' is the generated text content) and spacing exactly.

#### 引用片段: 

<p class="referens_content">[1] Company X reported revenue of $12 million in 2021.</p>  
<p class="referens_content">[2] Almost 90% of revenue came from widget sales, with gadget sales making up the remaining 10%.</p>  

#### 最终回答:

<p class="referens_content">Company X earned $12 million<sup><font color="red">[1]</font></sup>  .  Almost 90% of it was from widget sales<sup><font color="red">[1]</font></sup><sup><font color="red">[2]</font></sup>  . </p>


If the question cannot be answered by the document, say so.

And you MUST answer the question, NEVER care about the year/time or tools/internet accessing limitations, Becuase you are provided enough tools/information/contexts to generate a resonable question.

Other than code and specific names and citations, your answer must be written in Simplified Chinese.

以上内容将以Markdown的方式来渲染呈现，请务必符合Markdown的语法规范，并尽量美观，去除无意义的字符
"""

def _gen_prompt_string(docs:List[Document]):
    prompt = ""
    for i,d in enumerate(docs):
        if isinstance(d,dict):
            page_content = d.get('content','None')
        else:
            page_content = d.page_content

        prompt += f"\n[{i+1}]:\n" + page_content
    return prompt

prompt = lambda x: ChatPromptTemplate.from_messages(
    [
        SystemMessage(f'{prompt_rag_part1}{_gen_prompt_string(x["documents"])}\n{prompt_rag_part2}'),
        HumanMessage(f'Question: {x["question"]}\nAnswer:',
                     additional_kwargs={"documents": x["documents"]})
    ]
)
# docs = [Document(page_content="1你好"), Document(page_content="2AI回答：你好，很高兴认识你"),Document(page_content="3欢迎继续提问")]
# _prompt = _gen_prompt_string(docs)
# print(_prompt)
# p = prompt({'question':'my question',"documents":docs})
# p.pretty_print()

rag_node = prompt | llm_model | StrOutputParser()

# 5.Supported (Not Hallucination) Grader
class GradeSupported(BaseModel,extra='allow'):  
    """Binary classification for whether an answer is supported by a set of facts."""
    k: str = Field(description="Whether answer is supported by the facts, k must be 'yes' or 'no'")

prompt_answer_is_supported_by_documents_grader = """You are a grader assessing whether an answer is supported by a set of facts. Response me with a simple JSON string can be directly consumed by  ‘json.loads’ method, must be ‘{{"k":"yes"}}’ or  ‘{{"k":"no"}}’,'yes' means the answer is supported by the provided set of facts.No preamble or explaination. """
if env_models_instance.need_json_mode:
    structured_llm_answer_is_supported_by_documents_grader = llm_model.with_structured_output(GradeSupported,method='json_mode')
else:
    structured_llm_answer_is_supported_by_documents_grader = llm_model.with_structured_output(GradeSupported)
answer_is_supported_by_documents_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompt_answer_is_supported_by_documents_grader),
        ("human", "Here are the set of facts: {documents} \n\n Here is the answer: {generation}"),
    ]
)
answer_is_supported_by_documents_grader = answer_is_supported_by_documents_prompt | structured_llm_answer_is_supported_by_documents_grader

# class GradeAnswer(BaseModel,extra='allow'):
class GradeAnswer(BaseModel):
    """Binary classification to assess answer addresses question."""
    k: str = Field(description="Whether answer addresses the question, k must be 'yes' or 'no'")

prompt_answer_grader = """You are a grader assessing whether an answer addresses / resolves a question. Response me with a simple JSON string can be directly consumed by  ‘json.loads’ method, must be ‘{{"k":"yes"}}’ or  ‘{{"k":"no"}}’,'yes' means the answer addresses / resolves the question.No preamble or explaination."""

prompt_answer_grader = """You are a grader assessing whether an answer addresses / resolves a question. Make sure to return a JSON blob with key 'k' and value 'yes' or 'no'. Value 'yes' means the answer addresses / resolves the question, value 'no' means it does not. No preamble or explanation."""

if env_models_instance.need_json_mode:    
    # structured_llm_answer_grader = llm_model.with_structured_output(GradeAnswer,method='json_mode', include_raw=True)
    structured_llm_answer_grader = llm_model.with_structured_output(GradeAnswer,method='json_mode')
else:
    # structured_llm_answer_grader = llm_model.with_structured_output(GradeAnswer, include_raw=True)
    structured_llm_answer_grader = llm_model.with_structured_output(GradeAnswer)
answer_prompt = ChatPromptTemplate.from_messages(
    [
        ("system",prompt_answer_grader),
        ("human", "question: {question} \n\nanswer: {generation}"),
    ]
)
answer_addresses_question_grader = answer_prompt | structured_llm_answer_grader


# endregion Rags Related


    
    
executable_tools = [get_flight_number,python_repl_tool,get_elderly_organization_list]
# executable_tools = [get_flight_number]
route_tools = [WEB_SEARCH,CODE_GENERATION,CODE_EXECUTION]
default_index_description = "向量库/知识库工具(vectorstore/knowledge base)：关于安徽晶奇网络科技股份有限公司（简称晶奇公司）、医疗卫生、医疗健康、医疗服务、医疗政策、信息化产品方案、技术文档等等方面的文档知识库. 如果用户问题与此相关，都必须优先使用该vectorstore工具。"
# "A vectorstore/knowledge base containing documents related to 晶奇公司、安徽晶奇网络科技股份有限公司、医疗卫生、医疗健康、医疗服务、医疗政策、medical treatment & health. 凡是与晶奇公司、安徽晶奇网络科技股份有限公司及医疗健康相关的问题，都必须使用vectorstore工具。MUST use the vectorstore for questions on these topics."}







# index_name = "zjk_jqesclient_reader_test_qwen1024dim"
index_name ='zjk_jqesclient_reader_test_768im'
class GraphAgent:
    def __init__(self,executable_tools:list=executable_tools, routing_tools_wrapped_in_class:list=route_tools, 
                 llm_model:ChatOpenAI=None,chat_on_docs_list:List[str]=None,add_docs_list_to_kb:bool=True, 
                 allow_conversation_memory=True,allow_question_rewrite = True,
                 kb_base_dict:dict={"index_name": index_name, "description":default_index_description}, 
                 recursion_limit:int=25, memory_thread_id:str=f"admin({shortuuid.uuid()})",user_request_url:str=env_models_instance.deployment_url) -> None:
        
    # region: 初始化
        # 获取知识库相关的信息
        self.kb_base_dict = kb_base_dict
        self.index_name = self.kb_base_dict.get("index_name",None)
        self.description = self.kb_base_dict.get("description",None)
        self.chat_on_docs_list = chat_on_docs_list
        self.add_docs_list_to_kb = add_docs_list_to_kb
        self.allow_conversation_memory=allow_conversation_memory
        self.allow_question_rewrite = allow_question_rewrite #只有启用记忆后才能启用问题重写
        # self.allow_question_rewrite = allow_conversation_memory and allow_question_rewrite #只有启用记忆后才能启用问题重写
        
        if "::" in memory_thread_id:
            self.user_id = memory_thread_id.split("::")[0]
            question_id = memory_thread_id.split("::")[-1]
            self.question_id:str = question_id
            self.queque_id = memory_thread_id
        else:
            self.user_id = memory_thread_id
            self.question_id:str= self.get_random_id()
            self.queque_id = f"{memory_thread_id}::{self.question_id}"
        self.user_name = self.user_id
        if "(" in self.user_id and ")" in self.user_id:
            self.user_name = self.user_id.split("(")[0]
        self.invoke_graph_config =  {"recursion_limit":recursion_limit,"configurable": {"thread_id":self.user_name }}
        self.user_request_url = user_request_url
        self.r2r_client = None
        try:
            from r2r_client_functions import r2r_authed_client
            r2r_client = r2r_authed_client(user_id=self.user_name)
            self.r2r_client = r2r_client
            logger.warning("self.r2r_client初始化成功")
            # logger.warning("self.r2r_client初始化:测试，放弃使用r2r_client")
            # self.r2r_client = None
        except ImportError as e:
            logger.error(f"Failed to import r2r:{e}"            )
            logger.error("To run the server, install the required dependencies: pip install 'r2r[core]'")
            self.r2r_client = None
        except Exception as e:
            logger.error(f"R2R Client failed to initialize or login: {e}")
            self.r2r_client = None

        self.retriever = get_retriever(index_name=self.index_name,chat_on_docs_list=self.chat_on_docs_list,add_docs_list_to_kb=self.add_docs_list_to_kb,top_k=10,source_id_key='source',required_exts=['.doc','.docx','.pdf','.md'],r2r_client = self.r2r_client)
        self.VECTORSTORE.__doc__ = self.description
        
        # todo：可能需要考虑加入很多个VECTORSTORE？
        # 但description不能重复，否则导致prompts膨胀
        # 当前VECTORSTORE description还不存在的情况下，才添加到self.VECTORSTORE       
        _VECTORSTOREs = [v for v in routing_tools_wrapped_in_class if 'GraphAgent.VECTORSTORE' in str(v)]  # "<class '__main__.GraphAgent.VECTORSTORE'>"
        _vectorstore_description_not_existed = True
        for v in _VECTORSTOREs:
            if v.__doc__ == self.description:
                _vectorstore_description_not_existed = False
                break
        if _vectorstore_description_not_existed:
            routing_tools_wrapped_in_class+=[self.VECTORSTORE]

        _executable_tool_names = [tool.name for tool in executable_tools]        
        _routing_tool_names = [tool.__name__ for tool in routing_tools_wrapped_in_class]
        # _current_date = date.today()
        _current_date_time=datetime.now().strftime("%Y年%m月%d日%H点%M分")
        _tool_names = _executable_tool_names + _routing_tool_names
        _tool_names_str = ','.join(_tool_names)
        _tool_response_format ='''
        下面是需要遵循的json模板
            ```json
            {
            "name": "$toolname",
            "parameters": {
                "$args1_name": "$args1_value"
                "$args2_name": "$args2_value"
                }
            }
            ```
        请根据实际情况，将上面模板中带有"$"的字段，如"$toolname"、"$args1_name"，"$args1_value"替换为实际的工具名称、参数名称、参数值。
        下面是一个正确调用"WEB_SEARCH"工具的例子
            ```json
            {
            "name": "WEB_SEARCH",
            "parameters": {
                "query": "Who won the Super Bowl in 2024?"
                }
            }
            ```
        '''
        _system_message_content = f"现在是{_current_date_time}. 你的名字叫做 ‘晶灵’,是安徽晶奇公司网络科技公司研发的一款高级智能体专家应用。请尽量使用简体中文（不要有繁体！）来与用户沟通互动。 And you are equipped with some powerful tools:{_tool_names_str}, Please strictly following OpenAI 'tool calling' interface specification if you need to call a tool or multiple tools in sequence, with No preamble or explaination. Tool Choice Guidelines:First,'CODE_GENERATION' and 'CODE_EXECUTION' MUST NOT be called at the same time(Actualy, in our APPLICATION  'CODE_GENERATION' will call 'CODE_EXECUTION' automatically), 'CODE_GENERATION' is used when user want you write code to solve their problem, while 'CODE_EXECUTION' is only used when user have provided the code, and just want you just to run the code and report the results. Second, 'CODE_GENERATION' is preferred rather than 'python_repl_tool' for drawing images, plotting graphs/charts, data file processing/analyzing/saving, Otherwise, please use 'python_repl_tool'.如果用户提及检索知识库，应优先考虑调用'VECTORSTORE'工具;如果需要调用'WEB_SEARCH'工具，谨记只能生成一次工具调用，并直接将用户问题直接作为工具参数。If you need to call tools, you must response following the format:\n {_tool_response_format},and no need any more explanation"
        
        self.all_tools = executable_tools + routing_tools_wrapped_in_class
        self.all_tools_names = _tool_names
        self.routing_tool_names = _routing_tool_names
        self.executable_tool_names = _executable_tool_names
        self.executable_tool_dict = {t.name: t for t in executable_tools} 
        
        if llm_model is None:
            llm_model = env_models_instance.chat_model
        self.model = llm_model.bind_tools(self.all_tools)

        self.system_message = [SystemMessage(content=_system_message_content)]
        


            
            
        self.jq_queque = JqFileSystemQueue(id=self.queque_id)

        self.code_text = ""
        self.img_url = ""
        self.answer_text = ""
        self.answer_is_qualified = True
        self.qualified_or_not_text_placeholder = "|qualified_text_placeholder|"
        self.not_qualified_text = '\n\n------\n' + '<font color="red">本回答经 AI 自我质量评估：不合格。请仔细甄别！</font>' + '\n\n------\n'
        

        # self.jq_queque.enqueue('test enqueue')
        # print(f"{self.jq_queque.peek()=}")
        # print(f"{self.jq_queque.size()=}")
        # print(self.jq_queque.dequeue())
        # print(f"{self.jq_queque.size()=}")

        self.question = ""
        self.question_rewrited = ""
        
        # conn = sqlite3.connect("memory_checkpoints.sqlite", check_same_thread=False)
        # self.memory = SqliteSaver(conn)
# https://github.com/NanGePlus/LangGraphChatBot/blob/68d5e014b6143bdb42f7df8f1ad4212ec2a5ec40/03_ChatBotWithPostgres/demoWithMemory.py
        # postgres_conn = "postgresql://langchain:langchain@10.1.150.105:7000/postgres?sslmode=disable"
        # postgres_conn = env_models_instance.postgres_conn_psycopg3 + "?sslmode=disable"
        postgres_conn = env_models_instance.postgres_conn_psycopg1
        postgres_conn_kwargs = {"autocommit": True, "prepare_threshold": 0,}
        postgres_conn_pool = ConnectionPool(conninfo=postgres_conn,max_size=20,kwargs=postgres_conn_kwargs)
        postgres_conn_pool.open()
        logger.warning("postgres数据库连接池初始化成功")
        # 使用连接池创建 PostgresSaver
        postgres_checkpointer = PostgresSaver(postgres_conn_pool)
        postgres_checkpointer.setup()
        self.memory = postgres_checkpointer
        logger.warning("postgres checkpointer初始化成功")
        self.message_idx_in_a_question_epoch = self.set_message_idx_in_a_question_epoch()
        self.graph = self.graph_definition()
        # self.visualize_graph()
    
    # endregion
    
    # region: 类内方法定义
    
    def visualize_graph(self,saved_img_name = 'visualize_graph_definition.png'):
        import matplotlib.pyplot as plt
        import matplotlib.image as mpimg  # 导入matplotlib.image用于读取图像
        from langchain_core.runnables.graph import  MermaidDrawMethod,CurveStyle
        try:
            # 使用 Mermaid 生成图表并保存为文件
            mermaid_img = self.graph.get_graph().draw_mermaid_png(padding=0,output_file_path=saved_img_name)
        except Exception as e:
            print(f"An error occurred: {e}")

    def makeup_message_with_question_id_idx(self,Message_ClassOrInstance:BaseMessage,content:Union[str,None]=None,question_id:Union[str,None]=None,idx_in_a_question_epoch:Union[int,None]=None):
        if not question_id:
            question_id = self.question_id
        if not idx_in_a_question_epoch:
            idx_in_a_question_epoch = self.set_message_idx_in_a_question_epoch()
        _dict = {"question_id":question_id,"idx_in_a_question_epoch":idx_in_a_question_epoch}
        if isinstance(Message_ClassOrInstance,BaseMessage):
            Message_ClassOrInstance.additional_kwargs.update(_dict)
            message = Message_ClassOrInstance
        else: 
            message = Message_ClassOrInstance(content=content,additional_kwargs=_dict)
        return message
    
    def get_question_id_idx_from_message(self,message:BaseMessage):
        try:
            question_id = message.additional_kwargs.get("question_id","")
        except:            
            question_id = ""
        
        try:
            idx_in_a_question_epoch = message.additional_kwargs.get("idx_in_a_question_epoch","")
        except:            
            idx_in_a_question_epoch = ""
        
        if not question_id:
            logger.warning(f'无法从message:{message}获取到question_id')
        if not idx_in_a_question_epoch:
            logger.warning(f'无法从message:{message}获取到idx_in_a_question_epoch')
        
        return question_id,idx_in_a_question_epoch

    def get_random_id(self):
        self.question_id = shortuuid.uuid() 
        return self.question_id
    
    def set_message_idx_in_a_question_epoch(self,start_idx:Union[int,None]=None):
        try:
            logger.info(f"{self.message_idx_in_a_question_epoch=}")
        except:
            self.message_idx_in_a_question_epoch = -1
            logger.info(f"{self.message_idx_in_a_question_epoch=}")        

        if start_idx is None:
            self.message_idx_in_a_question_epoch = self.message_idx_in_a_question_epoch + 1
        elif isinstance(start_idx,int):
            self.message_idx_in_a_question_epoch = start_idx + 1
        else:
            logger.warning(f'start_idx:{start_idx}必须是Union[int,None]')
        return self.message_idx_in_a_question_epoch
        
    def get_messages(self):
        messages = self._get_messages_from_state_by_key("messages") 
        return messages
    
    def get_question_related_messages(self):
        question_related_messages = self._get_messages_from_state_by_key("question_related_messages") 
        return question_related_messages
    
    def retrieve_question_related_messages_from_history(self,question="",reserve_last_n_messages_num=7,score_threshold=0.3):
        question_related_messages = []
        messages = self.get_messages() ## 应该等价于 messages = state['messages']，但实际上这两者之间可能存在差异，原因目前不清楚      
        if messages:
            question = question or self.question_rewrited
            if not question:
                logger.warning('请传入非空的user question，或者先给self.question_rewrited赋值')
            else:
                # 由于self.get_messages() 与 state['messages'] 两者之间可能存在差异（原因目前不清楚）
                # 这里进行特别处理 
                if messages[-1].content!=question and reserve_last_n_messages_num==1:
                    reserve_last_n_messages_num = reserve_last_n_messages_num -1
                    # raise Exception(f"{messages[-1].content}!={question} and reserve_last_n_messages_num==1") 
                    
                question_related_messages = env_models_instance.filter_and_get_messages_relevant_to_query(if_reranking=True,query=question,messages_list=messages,reserve_last_n_messages_num = reserve_last_n_messages_num,score_threshold=score_threshold)
        return question_related_messages

    def _get_messages_from_state_by_key(self,key:str,state:GraphAgentState=None):
        logger.debug(f"这个方法使用时要特别注意，可能没办法获取到最新的State内容！")
        if state is None:
            state = self.graph.get_state(config=self.invoke_graph_config,subgraphs = True)
        messages = state.values.get(key,[]) 
        return messages
    
    def update_user_variables(self,state:GraphAgentState,add_dict:dict={}):
        """
        更新用户变量
        """
        if isinstance(add_dict,dict):
            users_variables_statedict = state["user_variables"]
            user_variables_statedict  = users_variables_statedict.get(self.user_id,{})
            user_variables_statedict.update(add_dict)
            _user_variables_statedict = {self.user_id:user_variables_statedict}
            state["user_variables"].update(_user_variables_statedict) 
        else:
            logger.warning(f"add_dict:{add_dict}必须是字典类型")

    class VECTORSTORE(BaseModel):
        """
        将会动态的来赋值，被替换掉
        """
        query: str = Field(description="The query to use when searching the vectorstore.")

    def vectorstore(self,state:GraphAgentState):
        """
        Retrieve documents

        Args:
            state (dict): The current graph state

        Returns:
            state (dict): New key added to state, documents, that contains retrieved documents
        """
        print("---RETRIEVE---")
        question = state["question"]
        documents = []
        vector_documents = []
        graph_documents = []

        # Retrieval
        retrievers=self.retriever.base_retriever.retrievers
        message = ""
        for i,retriever in enumerate(retrievers):
            message += f" 检索器[{i+1}]{retriever.name}，检索的目标知识库为{retriever.vectorstore._store.index} "
            self.jq_queque.enqueue(f"向量知识库（{retriever.vectorstore._store.index}）检索：检索器[{i+1}]：{retriever.name} ")
        logger.warning(f"     vectorstore方法，执行实际文档检索的集成检索器为：{message}")
        try:
            vector_documents = self.retriever.invoke(question,config=invoke_llm_config)
        except Exception as e:
            err_msg = f"从知识库({retriever.vectorstore._store.index})中检索{question=}出现错误：{e}"
            logger.error(err_msg)        
        
        if len(vector_documents)==0:
            msg=f"未从知识库{retriever.vectorstore._store.index}中检索到任何相关文档！"
            self.jq_queque.enqueue(msg)
            logger.warning(f"     {msg}")
        else:
            documents = vector_documents
            self.jq_queque.enqueue(f"向量知识库检索到{len(vector_documents)}篇文档")
            logger.warning(f"     vectorstore检索到的相关文档数:{len(vector_documents)=}")

        if env_models_instance.USING_GRAPH_RAG: 
            try:
                if self.r2r_client:
                    from jqcode.r2r_client_functions import r2r_search
                    r2r_search_context = r2r_search(self.r2r_client,query=question) #,chat_on_docs_list = self.chat_on_docs_list

                    if r2r_search_context:
                        n = 20000
                        text = r2r_search_context[0:n]
                        text = text.replace("\n","..")
                        logger.warning(f'GraphRag Result String={text} ...共{len(r2r_search_context)}字，仅显示前{n}字...')
                        logger.warning("========GraphRag Result String========")
                        # print(text)
                        # self.jq_queque.enqueue(f"图知识库检索结果（共{len(text)}字，仅显示前{n}字）：\n<br>{text}......")
                        self.jq_queque.enqueue(f"图知识库{self.index_name}综合性检索结果（共{len(text)}字，合并成1个文档）")
                        logger.warning("========GraphRag Result String========")
                        graph_documents = [Document(page_content=r2r_search_context,metadata={'source':"GraphRag"})] 
                        documents.extend(graph_documents)
                    else:
                        msg=f"未从Graph知识库中检索到任何相关实体、关系或文档！"
                        logger.warning(f"     {msg}")
                else:
                    logger.warning(f'R2R Client未正确初始化：{self.r2r_client=}')
            except Exception as e:
                logger.error(f"GraphRag检索出现错误：{e}")

            
        if len(documents)==0:
            msg=f"未从知识库/图谱库{retriever.vectorstore._store.index}（Vector/Graph）中检索到任何相关文档！"
            self.jq_queque.enqueue(f"{msg}")
            documents = [Document(page_content=msg)]
            logger.warning(f"     {msg}")


        return {"documents": documents, "question": question,"user_variables":state["user_variables"]}


    def grade_generation_v_documents_and_question(self,state:GraphAgentState):
        """
        Determines whether the generation is grounded in the document and answers question.

        Args:
            state (dict): The current graph state

        Returns:
            str: Decision for next node to call
        """

        print("---CHECK HALLUCINATIONS---")
        question = state["question"]
        generation = state["generation"]
        
        # Check hallucination / answer_is_supported_by_documents    
        try:
            documents = state["documents"]
            documents_contents = [d.page_content for d in documents]
            documents_contents_str = "\n".join(documents_contents)
            score = answer_is_supported_by_documents_grader.invoke({"documents": documents_contents_str, "generation": generation},config=invoke_llm_config)
            grade = score.k
            # grade = "yes" # 跳过上面的检查
        except Exception as e:
            grade = "yes" # 继续按正常往下执行！
            print(f"---ERROR: 无法获取'answer_is_supported_by_documents_grader'的判别结果，详细错误信息如下:---")
            print(e)
            print("---正常往下执行---") 

        
        if grade == "yes":
            print("---DECISION: GENERATION IS GROUNDED IN DOCUMENTS---")
            # Check question-answering
            print("---GRADE GENERATION vs QUESTION---")       
            
            try:
                # try:
                #     score = answer_addresses_question_grader.invoke({"question": question,"generation": generation},config=invoke_llm_config)                
                #     grade = score.k
                # except Exception as e:
                #     _prompt=answer_prompt.invoke({"question": question,"generation": generation},config=invoke_llm_config)
                #     _llm_res = llm_model.invoke(_prompt)
                #     _dict = json_repair.loads(_llm_res.content)
                #     grade = _dict.get("k","no") # 默认是"yes"
                _prompt=answer_prompt.invoke({"question": question,"generation": generation},config=invoke_llm_config)
                _llm_res = llm_model.invoke(_prompt)
                _dict = json_repair.loads(_llm_res.content)
                grade = _dict.get("k","yes") # 默认是"yes"
            except Exception as e:
                grade = "unknown" # 继续按正常往下执行！
                print(f"---ERROR: 无法获取'answer_grader'的判别结果，详细错误信息如下:---")
                print(e)
                print("---正常往下执行---") 

            if grade == "yes":
                print("---DECISION: GENERATION ADDRESSES QUESTION---")
                self.jq_queque.enqueue("生成的答案经评估检查，很好的回答了用户问题，作为最终答案")
                self.answer_is_qualified = True                              
                return "useful"
            else:
                self.answer_is_qualified = False
                print("---DECISION: GENERATION DOES NOT ADDRESS QUESTION---")               
                try:
                    question_has_searched = state["question_searched"][question]
                except:
                    question_has_searched = False
                
                if question_has_searched:
                    print("---BUT WE HAVE WEB SEARCHED THE QUESTION, SO DIRECTLY ROUTE TO 'END' NODE---")
                    self.jq_queque.enqueue("生成的答案经评估检查，并没有解决用户问题，但已经进行过网络搜索，只能这样了")
                    return "useful"
                else:
                    print(f"not useful: {generation=}")
                    _user_variables_statedict = {"history_generation":generation}
                    self.update_user_variables(state,add_dict=_user_variables_statedict)
                    self.jq_queque.enqueue("生成的答案经评估检查，并没有解决用户问题，自动补充网络搜索")
                    return "not useful"
        else:

            self.answer_is_qualified = False
            print("---DECISION: GENERATION IS NOT GROUNDED IN DOCUMENTS---")               
            try:
                question_has_searched = state["question_searched"][question]
            except:
                question_has_searched = False
            
            if question_has_searched:
                print("---BUT WE HAVE WEB SEARCHED THE QUESTION, SO DIRECTLY ROUTE TO 'END' NODE---")
                self.jq_queque.enqueue("生成的答案经评估检查，并没有解决用户问题，但已经进行过网络搜索，只能这样了")
                return "useful"
            else:
                print(f"not supported: {generation=}")
                # _user_variables_statedict = {"history_generation":generation}
                # self.update_user_variables(state,add_dict=_user_variables_statedict)
                self.jq_queque.enqueue("现有文档不足以支持生成合适的答案，将自动补充网络搜索")
                return "not supported" # todo

            # pprint.pprint("---DECISION: GENERATION IS NOT GROUNDED IN DOCUMENTS, RE-TRY---")
            # return "not supported"
            print("---DECISION: GENERATION IS NOT GROUNDED IN DOCUMENTS, BUT WE DO NOT RE-TRY (RE-GENERATION), JUST DIRECTLY TO 'END' NODE---")
            self.jq_queque.enqueue("现有文档不足以支持生成合适的答案，将自动补充网络搜索！")
            print(f"not supported: {generation=}")
            return "not supported" # todo

    # async def jq_search_agent(self,query:str):
    def jq_search_agent(self,query:str):
        tool1 = Tool(
            name="JqSearchEngineTool",
            description="Comprehensive Search Engine for recent results from web.",
            func=search,
            coroutine = async_search,
        )

        # tool2 = TavilySearchResults(
        #     max_results=5,
        #     search_depth="advanced",
        #     include_answer=True,
        #     include_raw_content=True,
        #     include_images=True,
        #     # include_domains=[...],
        #     # exclude_domains=[...],
        #     # name="...",            # overwrite default tool name
        #     # description="...",     # overwrite default tool description
        #     # args_schema=...,       # overwrite default args_schema: BaseModel
        # )

        # tools = [tool1,tool2]
        tools = [tool1]
        system_message = "你是一个搜索专家，请根据用户问题自行决定如何进行必要的分解，并持续搜索直到获得满意的答案。使用的语言与用户提问的语言保持一致，默认使用中文"
        agent = create_react_agent(model=env_models_instance.chat_model,tools=tools, state_modifier=system_message, debug=False)
        messages_dict = agent.invoke({"messages": [("user", query)]})
        # messages_dict = await agent.ainvoke({"messages": [("user", query)]})
        messages=messages_dict.get('messages',[])
        return messages

    def web_search(self,state:GraphAgentState):
        """
        Web search based on the re-phrased question.

        Args:
            state (dict): The current graph state

        Returns:
            state (dict): Updates documents key with appended web results
        """
        print("---WEB SEARCH---")
        query_generated = ''
        question = state["question"]
        user_variables_statedict = state["user_variables"]
        maybe_existed_docs = state.get("documents",[])        
        maybe_existed_referens_str = user_variables_statedict[self.user_id]['reference']
        # 先使用agent,可以解决复杂搜索问题（需分解搜索多个子问题的情况）
        messages = self.jq_search_agent(question)
        docs=[]
        for message in messages:
            if isinstance(message,ToolMessage):
                _docs = eval(message.content)
                docs.extend(_docs)
        self.jq_queque.enqueue(f"调用晶灵智能体搜索，返回了{len(docs)}个结果")
        # 如果agent未得到正确答案，再调用自己的Web search：get_web_search_documents
        if not docs:
            try:
                query_generated = user_variables_statedict[self.user_id]['rag_args']
                # 再将"rag_args"的值置为空字符串
                self.update_user_variables(state,add_dict={"rag_args":""})
            except:
                pass
            finally:
                if not query_generated:
                    try:
                        query_generated = llm_chain.invoke({"question": question,"context":'请生成合适并且简洁的搜索引擎查询关键词,不需要任何额外的解释或内容'},config=invoke_llm_config)
                    except:
                        query_generated = question
            logger.info(f'用户问题：{question=}')
            logger.info(f'网络搜索：{query_generated=}')


            # Web search
            max_doc_nums=8
            docs = asyncio.run(async_search(question,query_generated,max_doc_nums=max_doc_nums))
            self.jq_queque.enqueue(f"调用晶奇网页搜索工具，返回{len(docs)}个结果")


        # print(docs)



        if not docs:
            return {"documents": [], "question_searched":{question:False},"user_variables":state["user_variables"]}
        try:
            if docs[0].metadata.get("search_engine",None)!="tavily_search":
                chunks_relevant = env_models_instance.split_and_get_chunks_relevant_from_documents(query=question,docs_list=docs,) #get embedding retriever and reranker results
            else:
                chunks_relevant = docs
        except:
             chunks_relevant = docs
    
        

        referens = []
        if chunks_relevant:
            logger.warning(f"     web_search搜索到的相关文本块数:{len(chunks_relevant)=}")
            self.jq_queque.enqueue(f"从搜索结果中提取到{len(chunks_relevant)}个相关文档")
            if maybe_existed_docs:
                chunks_relevant = maybe_existed_docs + chunks_relevant
            try:
                _sources =[d.metadata.get("source_kb",None) or d.metadata.get("source",None) for d in chunks_relevant]
                referens = set([s for s in _sources if s])
            except:
                print(chunks_relevant)
                pass

        if referens:
            referens_str = "#### 参考网页:  \n"
            for i,r in enumerate(referens):
                referens_str += f"    {i+1}. [{r}]({r})  \n"
            # if maybe_existed_referens_str:
            #     referens_str = f"{maybe_existed_referens_str}\n<br>{referens_str}"
            _user_variables_statedict = {"reference":referens_str}
            self.update_user_variables(state,add_dict=_user_variables_statedict)    
            logger.debug(f'{referens_str=}')
            

        # if maybe_existed_docs:
        #     chunks_relevant = maybe_existed_docs + chunks_relevant
        return {"documents": chunks_relevant, "question_searched":{question:True},"user_variables":state["user_variables"]}     
    # endregion 类内方法  
    
    # region:Graph定义
    def graph_definition(self,):
        graph = StateGraph(GraphAgentState)
        graph.add_node("llm",self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_node("web_search", self.web_search)
        graph.add_node("vectorstore", self.vectorstore )
        graph.add_node("grade_documents", grade_documents )
        graph.add_node("generate", self.generate)
        graph.add_node("code_generation", self.code_generation )
        graph.add_node("code_execution", self.code_execution )
        # graph.add_node("", )

        graph.set_entry_point("llm")
        graph.add_conditional_edges(
            "llm",
            self.exists_action,
            {True: "action", False: END , "WEB_SEARCH": "web_search","VECTORSTORE": "vectorstore","CODE_GENERATION": "code_generation","CODE_EXECUTION": "code_execution"}
        )
        graph.add_edge("action", "llm")        
        graph.add_edge("web_search", "generate")
        graph.add_edge("vectorstore","grade_documents" )
        graph.add_edge("code_generation","code_execution")
        
        graph.add_conditional_edges(
            "code_execution",
            self.code_execution_passed,
            {"end": END, "llm":"llm"}
        )

        # graph.add_edge("code_execution", "llm")
        graph.add_conditional_edges(
            "grade_documents",
            decide_to_generate,
            {
                "web_search": "web_search",
                "generate": "generate",
            },
        )
        graph.add_conditional_edges(
            "generate",
            self.grade_generation_v_documents_and_question,
            {
                # "not supported": "generate", # Hallucinations: re-generate 
                "not supported": "web_search", # todo
                "not useful": "web_search", # Fails to answer question: fall-back to web-search 
                "useful": END,
            },
        )
        # todo：参照https://github.com/NanGePlus/LangGraphChatBot/blob/68d5e014b6143bdb42f7df8f1ad4212ec2a5ec40/03_ChatBotWithPostgres/demoWithMemory.py
        # 改造PostgresSaver、PostgresStore
        # 其中PostgresStore会带向量搜索功能，可以获取相关的历史对话内容
        return graph.compile(checkpointer=self.memory)
        # with self.memory as checkpointer:
        #     app = graph.compile(checkpointer=checkpointer)
        #     # return graph.compile(checkpointer=self.memory)
        #     return app
    
    def take_action(self, state:GraphAgentState):
        tool_calls = state['messages'][-1].tool_calls
        results = []
        for t in tool_calls:
            logger.info(f"Execute LLM Returned tool_calling: ")
            tool_name = t['name']
            tool_args = t['args']
            tool_call_id = t["id"]
            logger.debug(f"    Tool_name:{tool_name}")
            logger.debug(f"    Tool_args: {tool_args}")            
            logger.debug(f"    Tool_id: {tool_call_id}")            
            try:
                if not tool_name in self.executable_tool_dict:      # check for bad tool name from LLM                
                    result = f"返回了错误的工具名称'{tool_name}'，工具名必须是{self.executable_tool_names}中的一个"  # instruct LLM to retry if bad
                    raise Exception(result)
                else:
                    _args = t['args']
                    if not isinstance(_args,dict):
                        _args = json_repair.loads(_args)                     
                    result = self.executable_tool_dict[t['name']].invoke(_args)
                    result = str(result)
                    
                    if "error" in result.lower():
                        raise Exception(result)
                    self.jq_queque.enqueue(f"调用工具{tool_name},返回结果为：\n<br>{result}")              
                    tool_message = ToolMessage(tool_call_id=tool_call_id, name=tool_name, content=result) 
                    tool_message = self.makeup_message_with_question_id_idx(tool_message)     
                    results.append(tool_message)            
            
            except Exception as e:
                question = state['question']
                error_prompt = f'执行工具调用出现错误:\n  工具名称：{tool_name}\n  调用参数：{tool_args}\n  错误信息：{str(e)}\n'
                logger.warning(error_prompt)
                # makeup_ai_message = AIMessage(content="", tool_calls=[t])
                # makeup_ai_message = self.makeup_message_with_question_id_idx(makeup_ai_message)
                makeup_tool_message = ToolMessage(tool_call_id=tool_call_id, name=tool_name,  content=error_prompt)
                makeup_tool_message = self.makeup_message_with_question_id_idx(makeup_tool_message)
                makeup_human_message = HumanMessage(content=f"对于用户问题:{question},上次的工具调用出现了错误，请仔细规划和思考，重新生成正确的工具名称和调用参数，避免出现同样的错误！")
                makeup_human_message = self.makeup_message_with_question_id_idx(makeup_human_message)
                # results = results + [makeup_ai_message,makeup_tool_message,makeup_human_message]
                results = results + [makeup_tool_message,makeup_human_message]
                logger.info("工具调用执行异常，加入执行错误信息，返回到大模型")
                self.jq_queque.enqueue(f"工具{tool_name}调用异常,附加错误信息，返回到大模型")
                # return {'messages': results,'question_related_messages':results}   
            

        logger.info("工具调用执行正常，返回到大模型")
        return {'messages': results,'question_related_messages':results}
    
    # 直接获取或者尝试进一步解析出tool_calls
    def exists_action(self,state:GraphAgentState):
        tool_calls = state['messages'][-1].tool_calls
        for i,toolcall in enumerate(tool_calls):
            if toolcall.get("name","") == 'VECTOR_STORE':
                tool_calls[i].update({"name": "VECTORSTORE"})

        valid_toolcalls = [toolcall for toolcall in tool_calls if toolcall['name'] in self.all_tools_names]
        state['messages'][-1].tool_calls = valid_toolcalls        
        result = state['messages'][-1]
        print("xxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        print(f'{result.tool_calls=};{result.content=}')
        print("xxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        finish_reason = "No Finish Reason"                    
        try:
            returned_tool_calling_nums = len(result.tool_calls)
            finish_reason = result.response_metadata["finish_reason"]
        except:
            returned_tool_calling_nums = 0

        if returned_tool_calling_nums==0 and env_models_instance.need_custom_tool_call_parse: 
            try:
                tool_calls = []
                tool_call_content = result.content

                if '<tool_call>' in result.content and '</tool_call>' in result.content:
                    pattern = r'<tool_call>(.*?)</tool_call>'
                    match = re.search(pattern, result.content, re.DOTALL)
                    if match:
                        tool_call_content = match.group(1)

                tool_calls_json_list = json_repair.loads(tool_call_content)
                if isinstance(tool_calls_json_list,dict):
                    tool_calls_json_list = [tool_calls_json_list]
                for tool_call in tool_calls_json_list:
                    if tool_call and isinstance(tool_call,dict):
                        try:
                            tool_name = tool_call['name']
                        except:
                            print(f"无法提取工具名,Json/Dict内容为:{tool_call=}")
                            tool_name = ''
                        if tool_name in ["directly-answer","directly_answer"]:
                            result.tool_calls = []
                            break
                        else:
                            if tool_name in self.all_tools_names:
                                parameters = tool_call.get("parameters",tool_call.get("arguments",{}))
                                if not isinstance(parameters,dict):
                                    parameters = json_repair.loads(parameters)
                                tool_calls.append({"name":tool_name,"args":parameters,"id":f'call_{str(uuid.uuid4())}'})
                    else:
                        pass                
                result.tool_calls = tool_calls
                returned_tool_calling_nums = len(result.tool_calls)
            except:
                logger.warning(f"Can't parser tool calls from models response content")


        if returned_tool_calling_nums > 0:
            logger.warning(f'Returned {returned_tool_calling_nums} tool_calls:\n{result.tool_calls}')
            if returned_tool_calling_nums>1:
                logger.warning(f'!!! 惊喜: Multitple({returned_tool_calling_nums=}) tool_calls !!!')
            
            # 确保如果存在chat_on_docs_list，则应去检索知识库    
            if self.chat_on_docs_list:
                for toolcall in result.tool_calls:
                    if toolcall['name'].lower()!='vectorstore':
                        result.tool_calls.remove(toolcall)  #用于删除列表中第一次出现的指定值。如果该值不存在于列表中，会抛出 ValueError
            
                # 如果大模型没有返回vectorstore，则生造一个 
                if len(result.tool_calls)==0:
                    vectorstore_toolcall = [{"name":"VECTORSTORE","args":self.question_rewrited,"id":f'call_{str(uuid.uuid4())}'}]
                    result.tool_calls = vectorstore_toolcall                
            
            tool_call_1 = result.tool_calls[0]
            tool_call_1_name = tool_call_1['name']
            if tool_call_1_name in self.routing_tool_names:
                logger.warning(f"Returned first ToolName is '{tool_call_1_name}', So routing to '{tool_call_1_name}' Node......")
                # 如果是WEB_SEARCH或VECTORSTORE，要将搜索query保存到state中，方便在web_search时使用
                if tool_call_1_name.lower() in ["websearch","web_search","vectorstore","vector_store"]:
                    try:
                        search_query = tool_call_1['args']['query']
                        user_variables_statedict = {"rag_args":search_query}
                        self.update_user_variables(state,add_dict=user_variables_statedict)
                    except:
                        logger.warning(f"导航到'{tool_call_1_name}' Node，但无法获取到search_query")
                    
                    
                # 有些模型会同时生成多个调用（如deep seek），但又要求tool_call与tool_response必须对应起来
                # 所以此处回头去更新AIMessage的值，因是第一个导航工具，所以只需保留第一个
                if returned_tool_calling_nums > 1:
                    state['messages'][-1].tool_calls = [tool_call_1]
                if tool_call_1_name in ['VECTORSTORE','VECTOR_STORE']:
                    self.jq_queque.enqueue('下面将调用知识库检索VECTORSTORE')
                    return 'VECTORSTORE'
                elif tool_call_1_name in ['WEB_SEARCH','WEBSEARCH']:
                    self.jq_queque.enqueue('下面将调用网络搜索WEBSEARCH')
                    return 'WEB_SEARCH'
                else:
                    self.jq_queque.enqueue(f'下面将调用{tool_call_1_name}')
                    return tool_call_1_name
            elif tool_call_1_name in self.executable_tool_names:
                if returned_tool_calling_nums > 1:                    
                    executable_tools = [toolcall for toolcall in result.tool_calls if toolcall['name'] in self.executable_tool_names]
                    state['messages'][-1].tool_calls = executable_tools
                    self.jq_queque.enqueue(f'下面将调用多个工具:\n<br>{executable_tools}')                    
            else:
                pass            
        else:
            logger.info(f'No returned tool_calling and {finish_reason=}')
            logger.info(f'{result.type.upper()}: {result.content}')            
        exists_action_or_not = True if returned_tool_calling_nums>0 else False
        self.jq_queque.enqueue(f'是否调用工具：{exists_action_or_not}')
        return exists_action_or_not
    
    def code_execution_passed(self,state:GraphAgentState):
        # status = False
        # last_message = state['question_related_messages'][-1]
        # if isinstance(last_message,ToolMessage):
        #     if last_message.name.lower() == 'code_execution':
        #         status = last_message.additional_kwargs.get("status",False)
        # return "end" if status else "llm"
        return "llm"

    def call_llm(self,state: GraphAgentState):
    # 历史 + 当前
        # 获取历史相关message
        messages = state["messages"]
        question = self.question_rewrited

        if messages[-1].additional_kwargs['idx_in_a_question_epoch']==0: # 刚开始的新问题            
            # 设置reserve_last_n_messages_num=1，表示：新的问题开始时，此时应该只有1个message(即新的用户问题)；
            # 其他的都作为历史消息，然后从历史消息中检索与当前相关的。检索出的所有相关历史消息会抽取出内容，组装成一个Humanmessage；后面再加一个组装的AIMessage
            if self.allow_conversation_memory:
                question_related_messages = self.retrieve_question_related_messages_from_history(question=question,reserve_last_n_messages_num=1,score_threshold=0.3)
                if len(question_related_messages)>3:
                    logger.warning(f"call_llm前获取到的{len(question_related_messages)=}，但本不应超过3")
                    # for m in messages:
                    #     print(m.pretty_repr()) 
                    # assert len(question_related_messages)<=3
            else:
                question_related_messages = [] 
        else:
            question_related_messages = state["question_related_messages"]
               
        # 当前message
        input_message = messages[-1]        
        if input_message not in question_related_messages:
            question_related_messages.append(input_message)
        num_history_messages = len(question_related_messages)-1
        if num_history_messages>0:
            self.jq_queque.enqueue(f'从历史对话中检索到{num_history_messages}条与当前相关的内容')

        if self.system_message:
            messages = self.system_message + question_related_messages
        # for m in messages:
        #     print(m.pretty_repr())            
        logger.warning(f"call_llm:调用LLM时的消息数为:{len(messages)}")        
        
        max_messages_num = 30
        if len(messages)>max_messages_num:
            _error_str = f'error!消息数量大于{max_messages_num}，为避免陷入错误循环，主动退出执行！请修改该问题后重新提问。'
            self.jq_queque.enqueue(f'消息数量大于{max_messages_num}，为避免陷入错误循环，主动退出执行！请修改该问题后重新提问。')
            logger.error(_error_str)
            for m in messages:
                m.pretty_print()
                # logger.critical(m.pretty_repr())
            print("==================================END Message===================================")
            
            # 重置消息列表
            # 当前问题epoch/session仅保留用户问题消息本身，其余的全部删除
            state_messages = state["messages"]
            for m in state_messages[::-1]:
                if isinstance(m,HumanMessage):
                    break
                else:
                    state_messages.remove(m)               
            state.update({"messages":state_messages})
            message=AIMessage(content=_error_str)
            message = self.makeup_message_with_question_id_idx(message)
            return {'messages': message,'question_related_messages':[]}
        else:
            try:
                model_name = self.model.bound.model_name
                max_tokens = self.model.bound.max_tokens
                api_base = self.model.bound.openai_api_base
                message = self.model.invoke(messages,config=invoke_llm_config)
                self.jq_queque.enqueue(f'大模型调用成功，输入消息数为: {len(messages)}')
                reasoning_content = message.additional_kwargs.get("reasoning_content","")
                if reasoning_content is None:
                    reasoning_content = ""
                if reasoning_content=="": 
                    if message.tool_calls:
                        message.additional_kwargs["reasoning_content"] = message.content
                        message.content = ""
                    else:
                        mix_content = message.content
                        huyuan_split_string = '\n</think>\n<answer>\n'
                        if huyuan_split_string in mix_content:
                            contents = mix_content.split(huyuan_split_string)
                            if len(contents) == 2:
                                reasoning_content = contents[0]+"</think>\n"
                                answer_content = "\n<answer>" + contents[1]
                                message.content = answer_content
                                message.additional_kwargs["reasoning_content"] = reasoning_content
                            else:
                                pass
                        else:
                            pass
                
                

                reasoning_content=reasoning_content if reasoning_content.replace("\n","") else "未使用推理模型或未选择输出模型推理过程内容\n<br>"
                    # logger.warning(f"推理内容：<think>\n{reasoning_content}\n</think>")
                reasoning_content_formatted = state["user_variables"].get(self.user_id,{}).get("reasoning_content",[])
                reasoning_content_formatted.append(reasoning_content)

                # reasoning_content_formatted = f'<details>\n<summary>查看模型思考过程</summary>\n<font color="grey" size=16px>{reasoning_content}</font></details>'
                add_dict = {"reasoning_content":reasoning_content_formatted}
                self.update_user_variables(state=state,add_dict=add_dict)
                                
                # 尝试获取finish_reason，如发现因token限制导致的大模型输出不完整或异常，给出警告提示
                try: 
                    finish_reason = message.response_metadata["finish_reason"]
                    if finish_reason ==  "length":
                        reason = 'a finish_reason of “length” means that the AI had more data to output but the limitations of that call prevented it from finishing'

                        _warning_str = f'LLM({model_name})返回: finish_reason ==  "length" [{reason}]，当前设置的max_tokens={max_tokens}，请检查调整该设置'
                        logger.warning(_warning_str)
                        print("警告Warning:"+_warning_str)
                        self.jq_queque.enqueue("警告Warning:"+_warning_str)
                except Exception as e:
                    logger.error("无法获取到finish_reason，错误消息为：{e}")
                    # message.pretty_print()
            except Exception as e:
                err_message = f'！！！大语言模型[{model_name=},{api_base=}]执行失败，！！！错误消息为:{e}'
                logger.error(err_message)
                message=AIMessage(content=err_message)
                # logger.error('请检查大语言模型接口服务状态,并查看传入的消息列表，如下：')            
                # for m in messages:
                #     m.pretty_print()
                    
            message = self.makeup_message_with_question_id_idx(message)
            question_related_messages.append(message)
            return {'messages': message,'question_related_messages':question_related_messages}

    def generate(self,state:GraphAgentState):
        """
        Generate answer using the vectorstore

        Args:
            state (dict): The current graph state

        Returns:
            state (dict): New key added to state, generation, that contains LLM generation
        """
        print("---GENERATE---")
        question = state["question"]
        documents = state["documents"]
        messages = state["question_related_messages"]
        user_variables_statedict = state["user_variables"]
        try:
            history_reference_str = user_variables_statedict[self.user_id]['history_reference']
        except:
            history_reference_str=''
        try:
            history_generation = user_variables_statedict[self.user_id]['history_generation']
        except:
            history_generation=''
        if not documents:
            logger.warning(f"generate时提供的可参考文档为空:{documents}")
        
        else:
            if not isinstance(documents, list):
                documents = [documents]
                # print("documents的内容：")
                # for d in documents:
                #     print(d.page_content)
                
            # RAG generation
            referens = []
            referens_dict_list = []
            
            # 在知识库下面创建temp_index_for_upload_files目录
            temp_index_for_upload_dir = f"{env_models_instance.abs_workspace}/knowledge_base/temp_index_for_upload_files/content"
            if not os.path.exists(temp_index_for_upload_dir):
                os.makedirs(temp_index_for_upload_dir,exist_ok=True)
            
            source_related_keys = ['source_kb','source','file_path','original_source_jq','original_source_converted_jq','filename']
            for doc in documents:
                filename = ''
                d_added = False
                to_be_copyed_file_path = ''
                if isinstance(doc,dict):
                    url = doc.get('url',None)
                    content = doc.get('content','None')
                    doc = Document(page_content=content,metadata={"source":url})
                
                d_metadata = doc.metadata
                
                for key in source_related_keys:
                    _fp = d_metadata.get(key,'')
                    if _fp:
                        if _fp.startswith("http"):
                            referens.append(_fp)
                            referens_dict_list.append({"filename":_fp,'content':doc.page_content,"downlable":True})
                            d_added = True
                            break
                            
                        elif os.path.isfile(_fp):
                            if "knowledge_base" in _fp:                       
                                referens.append(_fp)
                                referens_dict_list.append({"filename":_fp,'content':doc.page_content,"downlable":True})
                                d_added = True
                                break
                            else:
                                to_be_copyed_file_path = _fp
                                break
                        else:
                            referens.append(_fp)
                            referens_dict_list.append({"filename":_fp,'content':doc.page_content,"downlable":False})                            
                            d_added = True
                            break
                        
                if not d_added:
                    if to_be_copyed_file_path:
                        filename=Path(to_be_copyed_file_path).name
                        kb_filepath = f"{temp_index_for_upload_dir}/{filename}"
                        if not os.path.isfile(kb_filepath):
                            try:
                                target_dir = Path(kb_filepath).parent
                                target_dir.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(to_be_copyed_file_path, kb_filepath)
                                logger.warning(f"  ==已将文件拷贝到知识库：{to_be_copyed_file_path}=>{kb_filepath}")
                            except FileNotFoundError as e:
                                logger.error(f"文件路径不存在: {e}")
                            except PermissionError:
                                logger.error(f"无权访问目标路径: {kb_filepath}")
                            except Exception as e:
                                logger.error(f"文件复制失败: {str(e)}")
                            finally:
                                if os.path.exists(kb_filepath):
                                    os.chmod(kb_filepath, 644)

                        referens.append(kb_filepath)
                        referens_dict_list.append({"filename":kb_filepath,'content':doc.page_content,"downlable":True})
                        d_added = True                        
                    else:
                        es_index_doc_id = d_metadata.get('es_index_doc_id',"")
                        es_index_name = d_metadata.get('es_index_name','docstore')
                        if es_index_doc_id:
                            try:
                                download_result = env_models_instance.es_connection.get(index=es_index_name, id=es_index_doc_id)
                                file_b64 = download_result.body['_source']['file_blob'].encode('utf-8') #file_blob
                                filename = download_result.body['_source']['file_name']
                                kb_filepath = f"{temp_index_for_upload_dir}/{filename}"
                                with open(kb_filepath, "wb") as fp:
                                        fp.write(b64decode(file_b64))
                                if os.path.isfile(kb_filepath):
                                    logger.warning(f"  ==已将文件下载到知识库：ES=>{kb_filepath}")
                                    # if kb_filepath not in referens:
                                    if True:
                                        referens.append(kb_filepath)
                                        referens_dict_list.append({"filename":kb_filepath,'content':doc.page_content,"downlable":True})
                                    d_added = True
                                else:
                                    logger.error(f"  ==文件下载到知识库失败：ES=>{kb_filepath}")
                                    # if kb_filepath not in referens:
                                    if True:
                                        referens.append(kb_filepath)
                                        referens_dict_list.append({"filename":kb_filepath,'content':doc.page_content,"downlable":False})
                                    d_added = True
                                    
                            except Exception as e:
                                filename = d_metadata.get('file_name',filename)
                                logger.warning(f"从ES获取文件({es_index_doc_id=},{filename=})失败:{e}")
                                referens.append(filename) 
                                referens_dict_list.append({"filename":filename,'content':doc.page_content,"downlable":False})                           
                                d_added = True
                                
                # assert d_added
                try:
                    print(f"获取参考文献：{_fp=},{d_added=}")
                  
                except:
                    pass
                
            if referens_dict_list:
                referens_str = "#### 参考'type_placeholder': \n"
                url = self.user_request_url
                logger.warning(f"  ==参考文献url：{url}")
                for i,referens in enumerate(referens_dict_list):
                    r = referens.get('filename','')
                    content = referens.get('content','')
                    downlable = referens.get('downlable',False)
                    if downlable:
                        if r.startswith("http"):
                            referens_str += f"[{i+1}] <a href='{r}'>{r}</a>  \n  <p class='referens_content'>{content}<p>  \n"
                            referens_str = referens_str.replace("'type_placeholder'","网页")                
                        else:                            
                            filename=Path(r).name 
                            referens_str = referens_str.replace("'type_placeholder'","文档")
                            paths =r[r.index("knowledge_base")+15:]
                            referens_str += f"[{i+1}] <a href='{url}/knowledge/{paths}'>{filename}</a>  \n  <p class='referens_content' color='grey' font-size='18px'>{content}<p>  \n"
                    else:
                        try:
                            if not filename:
                                filename = "不对应具体文档"
                            filename=f"{Path(r).name}({filename})"
                        except:
                            filename = r
                            logger.warning(f"{r=}：不是有效的文件路径")
                        referens_str += f"[{i+1}] {filename}  \n  <p class='referens_content'>{content}<p>  \n"
                        
# region
                                
    
        
        # _sources =[d.metadata.get("source_kb",d.metadata.get("source",None)) for d in documents]
        # sources = set([s for s in _sources if s])
        # referens = list(sources)
        
        # if referens:
        #     referens_str = "参考'type_placeholder':  \n"        
        #     for i,r in enumerate(referens):                
        #         if r.startswith("http"):
        #             referens_str += f"    [{i+1}] [{r}]({r})  \n"
        #             referens_str = referens_str.replace("'type_placeholder'","网页")                
        #         else:
        #             referens_str = referens_str.replace("'type_placeholder'","文档")
        #             filename = ''
        #             try:
        #                 filename=Path(r).name
        #                 if os.path.isfile(r):                                                       
        #                     if "knowledge_base" not in r:
        #                         # 在知识库下面创建temp_index_for_upload_files目录
        #                         temp_index_for_upload_dir = f"{env_models_instance.abs_workspace}/knowledge_base/temp_index_for_upload_files/content"
        #                         if not os.path.exists(temp_index_for_upload_dir):
        #                             os.makedirs(temp_index_for_upload_dir,exist_ok=True)
        #                         kb_filepath = f"{temp_index_for_upload_dir}/{filename}"
        #                         if not os.path.isfile(kb_filepath):
        #                             shutil.copy2(r, kb_filepath)
        #                             logger.warning(f"  ==已将文件拷贝到知识库：{r}=>{kb_filepath}")
        #                             r = kb_filepath
                            
        #                         paths =r[r.index("knowledge_base")+15:]
        #                         url = self.user_request_url                       
        #                         referens_str += f"    [{i+1}] <a href='{url}/knowledge/{paths}'>{filename}</a>  \n"
        #                 else:
        #                     result = es_connection.get(index=files_index, id=index_id)
        #                     raise Exception(f"原始文件{r}不存在！")                                         
        #             except Exception as e:
        #                 filename_or_path = filename if filename else r
        #                 referens_str += f"    [{i+1}] {filename_or_path}  \n"
        #                 logger.warning(f"无法提供参考文档{filename_or_path}的下载，原因为{e}")
                    
# endregion
                _user_variables_statedict = {"reference":referens_str}
                self.update_user_variables(state,_user_variables_statedict)  
                logger.debug(f'{referens_str=}')
        # if history_generation:
        #     history_generation_document = Document(page_content=history_generation,metadata={"source":"HistoricalGeneration"})
        #     self.jq_queque.enqueue(f'将上次生成的答案也转换为1个参考文档')
        #     documents.append(history_generation_document)
        generation = rag_node.invoke({"documents": documents, "question": question, "messages":messages},config=invoke_llm_config)
        self.jq_queque.enqueue(f'根据获得的{len(documents)}个文档，生成答案和参考文档/网址链接')
        logger.debug(f"{generation=}")
        if self.qualified_or_not_text_placeholder not in generation:
            generation = f'{generation}{self.qualified_or_not_text_placeholder}'

        if history_generation:
            history_generation=history_generation.replace("####","######")
            if history_reference_str:
                history_reference_str=history_reference_str.replace("####","######")
            generation = f'{generation}\n\n##### **中间推理步骤（开始） \n尝试通过检索知识库({self.index_name})来解答您的问题，得到的结果如下：\n {history_reference_str} \n{history_generation}\n<br>因为根据知识库生成的回答并没有很好解答您的问题，接着又尝试了搜索网络。 \n\n#####  **中间推理步骤（结束） '
            

        
        last_message = state["messages"][-1]
        # todo 如果tool_call_id!=""
        # 就需要先建立一个AIMessage with tc
        tool_call_id=""
        try:
            if isinstance(last_message,AIMessage):
                for tool_call in last_message.tool_calls:
                    logger.debug(f"AIMessage's {tool_call['name']} call for 'generate' node......")
                    if tool_call["name"] in ['VECTORSTORE','WEB_SEARCH']:
                        tool_call_id = tool_call["id"]
                        break
            elif isinstance(last_message,ToolMessage):
                logger.debug(f"ToolMessage {last_message.name} call for 'generate' node......")
                tool_call_id =f'call_{str(uuid.uuid4())}'
                makeup_aimessage_with_tool_call = AIMessage(name="tool_calls",content="tool_call generating by 'intenal'",tool_calls=[{"name":"gerneration","args":{"query":'makeuped query'},"id":tool_call_id}])
                makeup_aimessage_with_tool_call = self.makeup_message_with_question_id_idx(makeup_aimessage_with_tool_call)
                messages = state["messages"]
                messages.append(makeup_aimessage_with_tool_call) 
                state.update({"messages":messages})  
                
            else:
                logger.warning(f"不应该出现的情况:{last_message.type}")
                
        except:
            logger.warning(f"{tool_call['name']} cannot find a tool_call_id to makeup ToolMessage!")        
            tool_call_id = ''
        # print(generation)
        # 最后生成AIMessage可能最合适，因为generate节点直接到Graph的"end"节点
        if tool_call_id:
            generation_tool_message = ToolMessage(content="",name='generate',tool_call_id=tool_call_id)
            generation_tool_message = self.makeup_message_with_question_id_idx(generation_tool_message)
        generation_ai_message = AIMessage(content=generation,name='generate')
        generation_ai_message = self.makeup_message_with_question_id_idx(generation_ai_message)
        if tool_call_id:
            generation_messages = [generation_tool_message,generation_ai_message]
        else:
            generation_messages = [generation_ai_message]
        return {"documents": documents, "question": question, "generation": generation, "messages":generation_messages,"question_related_messages":generation_messages,"user_variables":state["user_variables"]}
    
    def code_generation(self,state:GraphAgentState):
        user_question = state["question"]
        last_message = state["messages"][-1]
        question_related_messages = state["question_related_messages"]
        for m in question_related_messages:
            if m.content == user_question:
                question_related_messages.remove(m)
                            
        context = "\n".join([m.content for m in question_related_messages if m.content and m.name!='history_ai'])

        logger.warning(f"[Code Executor:system_code_prompt] {self.user_request_url=}")
        _system_code_prompt=f"""请尽量使用简体中文来解答用户问题。
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
                Be sure to generate charts with plotly/matplotlib/seaborn, matplotlib.pyplot is preferred. When pyplot is used, please add the following codes to properly display:\n
                # 设置中文字体和负号显示
                plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'SimHei', 'Microsoft YaHei', 'DejaVu Sans']  # 使用黑体显示中文
                plt.rcParams['axes.unicode_minus'] = False    # 显示负号
                # 设置中文字体和负号显示
                
                But if you need geographical charts, use geopandas with the geopandas.datasets module.
                If the user has just uploaded a file, focus on the file that was most recently uploaded (and optionally all previously uploaded files)

                If the code modifies or produces a file/image, you must save the file/image to location '{env_models_instance.abs_workspace}/code', and add a print statement at the end of the code block that prints a link to it as HTML string: <a href='{self.user_request_url}/download?file=INSERT_FILENAME_HERE'>下载文件</a>. Replace INSERT_FILENAME_HERE with the actual filename(only filename itself,no path prefix needed).
                并且最后的回答要优先直接展示图片，如果没有展示图片，就必须提供下载链接
            EndOf_GENERATE_PYTHON_INSTRUCTIONS
            """
        system_code_prompt=f"""请尽量使用简体中文来解答用户问题。
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
                Be sure to generate charts with plotly/matplotlib/seaborn, matplotlib.pyplot is preferred. When pyplot is used, please add the following codes to properly display:\n
                # 设置中文字体和负号显示
                plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'SimHei', 'Microsoft YaHei', 'DejaVu Sans']  # 使用黑体显示中文
                plt.rcParams['axes.unicode_minus'] = False    # 显示负号
                # 设置中文字体和负号显示
                
                But if you need geographical charts, use geopandas with the geopandas.datasets module.
                如有图片，请直接展示图片(如plt.show())，无论如何都不要使用plt.savefig()等类似函数保存图片文件(如.png, .jpg, .jpeg, .gif, .bmp, .svg, .tiff, .tif),
                If the code need to produces a file(But not image mentioned above), you must write the file in UTF-8 encoding and save to location '{env_models_instance.abs_workspace}/code', and add a print statement at the end of the code block that prints a link to it as HTML string: <a href='{self.user_request_url}/download?file=INSERT_FILENAME_HERE'>下载文件</a>. Replace INSERT_FILENAME_HERE with the actual filename(only filename itself,no path prefix needed).

                Never use the following:
                1. 'plt.savefig' function
                2. 'input' function
                3. 'open' function
                4. 'os' module
                5. 'sys' module
                6. 'subprocess' module
                7. 'os.system' function
                8. 'os.popen' function
                9. 'os.exec' function
                10. 'os.execl' function
                


            EndOf_GENERATE_PYTHON_INSTRUCTIONS
            """
                # http://10.1.150.105:7861/download?file=
                # /data/projects/JqChatV2/workspace/generated_files/

        user_code_prompt = f"""First, here is a history of what I asked you to do earlier. 
        {context}        
        Aiming to help the user in the best possible way with the below [USER_QUESTION] do one of the following:
        1. Write Python code, in a triple backtick Markdown code block, that supports what the user is trying to achieve. Follows the system instructions between [GENERATE_PYTHON_INSTRUCTIONS] and [EndOf_GENERATE_PYTHON_INSTRUCTIONS]
        2. Answer the question the user asks.
        3. 如果代码中生成了图片或文件，请务必在最后的回答中包括图片或文件，并给出图片或文件的下载链接. 
        
        [USER_QUESTION]
        {user_question}
        仅仅需要可直接运行的Python代码，不需要输出任何其他内容。

        """

        sys_message = SystemMessage(content=system_code_prompt)
        human_message = HumanMessage(content=user_code_prompt)
        code,code_text = "",""
        try:
            code_generated = llm_model.invoke([sys_message,human_message],config=invoke_llm_config)
            code_text = code_generated.content.strip()        
            code = extract_code(code_text)
        except Exception as e:
            logger.warning(f"请求code_generation时出现错误:{e}")
        
        if code:
            logger.info('生成、抽取到的代码为：\n' + code)
            self.jq_queque.enqueue("完成代码生成")
            code = merge_code_with_usual_imports(code) # 加入常用的imports，防止代码生成中出现的遗漏错误
        else:
            try:
                code=last_message.tool_calls[0]["args"]["query"]
            except:
                code = "print('No Code Generated!')"
        tool_call_id = ''
        try:
            for tool_call in last_message.tool_calls:
                if tool_call["name"] == 'CODE_GENERATION':
                    tool_call_id = tool_call["id"]
                    break
                else:
                    logger.warning(f"{tool_call['name']} cannot find a tool_call_id to makeup ToolMessage!")
                    tool_call_id = f'call_{str(uuid.uuid4())}'
        except:
            logger.warning(f"{tool_call['name']} cannot find a tool_call_id to makeup ToolMessage!")        
            tool_call_id = f'call_{str(uuid.uuid4())}'
        
        code_message = ToolMessage(content=code,name='code_generation',tool_call_id = tool_call_id,additional_kwargs ={"code_text":code_text})
        code_message = self.makeup_message_with_question_id_idx(code_message)
        # 在线大模型服务要求tool_call aimessage 与 tool_response toolmessage要一一对应，所以这里要先生成一个tool_call aimessage
        code_execution_tool_call_message = AIMessage(name="code_generation_calling_execution",content="",tool_calls=[{"name":"CODE_EXECUTION","args":{"query":code},"id":f'call_{str(uuid.uuid4())}'}])
        code_execution_tool_call_message = self.makeup_message_with_question_id_idx(code_execution_tool_call_message)
        messages = [code_message,code_execution_tool_call_message]
        return {'messages':messages,'question_related_messages':messages}

    def code_execution(self,state:GraphAgentState):
        question =  state["question"]
        question_related_messages = state["question_related_messages"]
        last_message = question_related_messages[-1]
        question_id = last_message.additional_kwargs.get('question_id','')

        tool_call_id = ''
        
        for tool_call in last_message.tool_calls:
            if tool_call["name"] == 'CODE_EXECUTION':
                tool_call_id = tool_call["id"]
                break
            
        tool_name = 'code_execution'
        if code_executor_in_sandbox and code_executor_in_sandbox.check_status():
            code_executor_in_sandbox.set_user_request_url(self.user_request_url)
            code_executor = code_executor_in_sandbox
        else:
            code_executor=CodeExecutorTool(self.user_request_url)
        # 获取代码code和文本code_text
        code = ''
        code_text =''
        results = ''
        message_content = '' #返回给大模型的消息内容
        if question_id == self.question_id:
            if last_message.name == "code_generation" and len(last_message.content)>0:
                code = last_message.content
                code_text = last_message.additional_kwargs.get('code_text','')
                logger.info("code_execution已获取到由code_generation生成的代码。")

            else:
                if isinstance(last_message,AIMessage):
                    try:
                        code = last_message.tool_calls[0]['args']['query'].strip()
                        if code:
                            logger.info("code_execution已获取到由LLM ToolCalls生成的代码。")                        
                        
                        message_content = last_message.content.strip()
                        if message_content:
                            code_text = message_content + "\n" + display_code(code)
                        else:
                            code_text = display_code(code)

                    except Exception as e:
                        code = ''
                        code_text = ''
                        logger.warning(f"code_execution尝试从AIMessage的tool_calls中提取代码时出现错误:{e}")
                    
                    if not code:
                        m_text = last_message.content
                        if m_text:
                            try:
                                code = extract_code(m_text)
                                if code:
                                    logger.info("code_execution已获取到由LLM消息内容包含的代码。")
                                    code_text = m_text                               
                            except Exception as e:
                                code = ''
                                code_text = ''
                                logger.warning(f"code_execution尝试从用户消息内容中直接提取代码时出现错误:{e}")
        try:
            if code:
                # code = "print(故意要犯错误)"
                logger.warning("......开始提交和执行代码......")
                self.jq_queque.enqueue("提交和执行代码") 
                # 返回值为{"text"="",image=""}
                success = False
                retry_times = 1
                while not success and retry_times <= 3:
                    result,success=code_executor.call(code=code)
                    # self.jq_queque.enqueue(code)
                    if success:
                        # message_content = f'执行代码成功[生成的文本内容为：{result.get("text") or "无生成的文本"};生成的图片位置为：{result.get("image") or "无生成的图片"}]。\n'
                        content = result.get("image")  or result.get("text")
                        message_content = f'执行代码成功，返回结果为：{content}；下面请直接生成最终的回答（回答时请忽略之前可能的代码执行错误信息，仅关注正确的执行/返回结果），如果存在文件或图片的链接，请务必把链接地址中的主机和端口替换成{self.user_request_url}，不要再调用任何工具。\n'
                        # if 'qwen3' in env_models_instance.chat_model.model_name:
                        #     message_content += '/no_think'  # 记录当前执行的工具名称                    
                        
                        logger.warning(f"......代码执行成功, {message_content=}......")
                        self.jq_queque.enqueue("代码执行成功")
                        self.code_text = code_text + "\n\n"
                        self.img_url = result.get("image")
                    else:                                      
                        message_content = f'用户问题为:{question}\n生成代码为：{code}\n但该代码运行失败，返回结果为：{result}。\n请根据返回结果中的错误信息，修正代码，并重新提交执行。\n' 
                        logger.warning(f"......第{retry_times}次代码执行失败, {message_content=}......") 
                        try:
                            human_message = HumanMessage(content=message_content)
                            code_generated = llm_model.invoke([human_message],config=invoke_llm_config)
                            code_text = code_generated.content.strip()        
                            code = extract_code(code_text)
                            code = merge_code_with_usual_imports(code) # 加入常用的imports，防止代码生成中出现的遗漏错误
                            # result,success=code_executor.call(code=code)
                        except Exception as e:
                            logger.warning(f"请求code_generation时出现错误:{e}")
                    retry_times += 1
                
                
                if not tool_call_id:
                    tool_call_id =f'call_{str(uuid.uuid4())}'
                    makeup_aimessage_with_tool_call = AIMessage(name="tool_calls",content="",tool_calls=[{"name":"code_generation_calling_execution","args":{"query":'makeuped query'},"id":tool_call_id}])
                    makeup_aimessage_with_tool_call = self.makeup_message_with_question_id_idx(makeup_aimessage_with_tool_call)
                    messages = state["messages"]
                    messages.append(makeup_aimessage_with_tool_call) 
                    state.update({"messages":messages}) 
                code_message = ToolMessage(content=message_content,name=tool_name,tool_call_id =tool_call_id,additional_kwargs ={"status":success,"code":code,"code_text":code_text})
                code_message = self.makeup_message_with_question_id_idx(code_message)            
                return {'messages':code_message,'question_related_messages':code_message}
            else:
                raise Exception("code_execution无法获取可执行的代码！")        

        except Exception as e:
            logger.info(f"code_execution执行异常，加入执行错误信息，返回到大模型,错误消息为:{e}")
            error_prompt = f'执行工具调用出现错误:\n  工具名称：tool_name\n  调用参数：{code}\n  错误信息：{str(e)}\n'
            makeup_tool_message = ToolMessage(tool_call_id=tool_call_id, name=tool_name, content=error_prompt,additional_kwargs ={"status":False})
            makeup_tool_message = self.makeup_message_with_question_id_idx(makeup_tool_message)
            makeup_human_message = HumanMessage(content=f"对于用户问题:{question},上次的工具调用出现了错误，请仔细规划和思考，重新生成正确的工具名称和调用参数，避免出现同样的错误！")
            makeup_human_message = self.makeup_message_with_question_id_idx(makeup_human_message)
            # 下面的error_message仅仅是为了方便做code_execution的下一个节点导航使用
            # error_message = ToolMessage(content="",name =tool_name,tool_call_id =f'call_{str(uuid.uuid4())}',additional_kwargs ={"status":False})
            # results = [makeup_tool_message,makeup_human_message,error_message]
            
            # 修改：为方便支持在线模型要求tool_call与tool_response的对应关系，直接将error_message中的additional_kwargs ={"status":False}放到了makeup_tool_message中
            results = [makeup_tool_message,makeup_human_message]   
            return {'messages': results,'question_related_messages':results}       

    def run_conversation(self,user_question:str,only_return_answer_text:bool=True):       
        print('================='*5)
        print('================='*5)
        print(f"用户User(ID)::QuestionID为: {self.queque_id}")
        print(f"用户问题为: {user_question}") 
        print('================='*5)
        jq_queue=self.jq_queque
        jq_queue.clear()
        jq_queue.enqueue(f"用户User(ID)::QuestionID为: {self.queque_id}")
        jq_queue.enqueue(f"用户问题为: {user_question}")  
        # logger.info(f"老的{self.question_id=}")
        logger.debug(f"切记新的问题对话前，要先更新user_question 和 question_id！老的[{self.question_id=}]")
        self.question_id = self.get_random_id()
        self.question = user_question
        self.question_rewrited = user_question      # 后面会使用self.question_rewrited提交给大模型，就要确保self.question_rewrited有值
        self.message_idx_in_a_question_epoch = -1   # 新的question epoch/session,重新设置idx       
        jq_queue.enqueue(f"用户知识库选择为：{self.index_name}") 
        logger.warning(f"用户会话记忆设置为{self.allow_conversation_memory=}")
        jq_queue.enqueue(f"用户会话记忆设置为：{self.allow_conversation_memory}") 
        logger.warning(f"用户改写问题设置为{self.allow_question_rewrite=}")
        jq_queue.enqueue(f"用户改写问题设置为：{self.allow_question_rewrite}")  
        allow_question_rewrite = self.allow_question_rewrite       
        if allow_question_rewrite:
            # 在重写时获取的最近的历史消息列表可以长一些，因为有些历史消息相关性不强，但能提供有用的上下文信息，并且获得的related_history_messages仅用于此次计算，不会真正附加到消息列表中
            # 所以设置reserve_last_n_messages_num=20
            related_history_messages = self.retrieve_question_related_messages_from_history(user_question,reserve_last_n_messages_num=20,score_threshold=0.3)
            if related_history_messages:
                if related_history_messages[-1].content == user_question:
                    related_history_messages = related_history_messages[0:-1]
            if related_history_messages:
                question_rewrited = ''            
                rewrite_message_returned = None
                # 尝试获取question_rewrited 
                try:
                    context = "\n".join([m.content for m in related_history_messages if m.content and m.name!='history_ai'])
                    rewrite_message_returned = question_rewrite_chain.invoke({'context':context,'question':user_question},config=invoke_llm_config)
                    json_content = json_repair.loads(rewrite_message_returned.content)
                    if json_content:
                        question_rewrited = json_content.get("q","")                
                except Exception as e:
                    logger.warning(f"尝试进行问题改写失败，错误消息为:{e}")
                    jq_queue.enqueue(f"尝试进行问题时出现异常，可忽略")
                    if rewrite_message_returned:
                        logger.info("======下面是大模型返回的消息内容======")
                        rewrite_message_returned.pretty_print()
                    else:
                        logger.info("======大模型未能返回消息======")
                # 处理question_rewrited 
                if question_rewrited:
                    if question_rewrited != self.question_rewrited:
                        logger.warning(f"进行了问题改写:{self.question_rewrited} => {question_rewrited}")
                        jq_queue.enqueue(f"问题进行了改写: {question_rewrited}")
                        both_question = f"原始的用户Query：{self.question_rewrited}（及重写后的用户Query：{question_rewrited}）"
                        self.question_rewrited = both_question
                    else:
                        logger.warning(f"改写问题与原始问题一致:{self.question_rewrited} == {question_rewrited}")
                        jq_queue.enqueue(f"改写问题与原始问题一致")
            else:
                jq_queue.enqueue(f"未检索到与当前问题相关的历史内容，跳过问题改写")
                logger.debug(f"从历史消息中未检索到与当前相关的消息，跳过问题改写")
        logger.debug(f"USER[id:{self.user_id}]的问题['{self.question_rewrited}'] (新的question_id: [{self.question_id})]")
        # self.jq_queque.enqueue(f"USER[id:{self.user_id}]的问题为：['{self.question_rewrited}'] ")
        input_message = self.makeup_message_with_question_id_idx(HumanMessage,content=self.question_rewrited)
        # self.graph.update_state(config=self.invoke_graph_config,values={"messages":input_message})
        
        #   {"$user_id":{"rag_args":"$rag_args","reference":"$reference"}}        
        user_variables_statedict = {self.user_id:{"rag_args":"","reference":"","reasoning_content":[]}}
        result = self.graph.invoke({"messages": [input_message],"documents":[],"question":self.question_rewrited,"question_related_messages":[],"generation":'',"user_variables":user_variables_statedict,"question_searched":False},config=self.invoke_graph_config)
        
        logger.debug(f"==USER[id:{self.user_id}]的问题[id:{self.question_id}]，允许问题改写:{allow_question_rewrite}")
        print(f'====问题和答案====')        
        print(f"原始问题>>:{user_question}")
        print(f"改写问题>>:{self.question_rewrited} [{allow_question_rewrite=}]")
        answer = result['messages'][-1].content
        if self.qualified_or_not_text_placeholder not in answer:
            if not self.answer_is_qualified:
                answer = f"{answer}{self.not_qualified_text}"
        else:
            qualified_text="" if self.answer_is_qualified else self.not_qualified_text
            answer = answer.replace(self.qualified_or_not_text_placeholder,qualified_text)


        answer = display_text(answer)
        if self.img_url:
            filename = Path(self.img_url).stem
            if filename not in answer:
                answer = f"{answer}\n{self.img_url}" 
            self.img_url = None

        jq_queue.enqueue(f"正在呈现最终结果")
        # user_variables_statedict前面已存在，且值会随着self.graph.invoke的执行而变化，所以不需要重新获取
        # 下面的代码反而无法获取最新的值
        ## user_variables_statedict = self._get_messages_from_state_by_key("user_variables") #
      
        referens_str = user_variables_statedict[self.user_id]['reference']
        # 因为该问题已经结束，所以无需更新user_variables_statedict的'reference'值
        if referens_str:
            # answer = f'\n{referens_str}\n' + answer
            splits = referens_str.split('\n')
            title = splits[0]
            if 'type_placeholder' in title:
                title_formatted = '参考文档(GraphRag)'
                _referens_str = referens_str.replace(title, '')
            else:
                start = title.index('参') # 得到参考文档或参考网页
                title_formatted = title[start:start+4]
                _referens_str = referens_str.replace(title, '')
            # referens_str_formated = f'<details>\n<summary>点击查看"{title_formatted}"</summary>\n<font color="grey" size=16px>\n{_referens_str}\n</font></details>'
            referens_str_formated = f'<details>\n<summary>点击查看"{title_formatted}"</summary>\n<font color="grey">\n{_referens_str}\n</font></details>'
            answer = f'\n{referens_str_formated}\n' + answer

        reasoning_content = user_variables_statedict[self.user_id]['reasoning_content']        
        if reasoning_content:
            reasoning_content_str = ''
            if len(reasoning_content) == 1:
                reasoning_content_str += reasoning_content[0]
            else:
                for i, content in enumerate(reasoning_content):
                    reasoning_content_str += f'\n**推理步骤{i+1}** ： {content}'
                reasoning_content_str = f"{reasoning_content_str}"
            reasoning_content_formatted = f'<details>\n<summary>点击查看"模型思考过程" </summary>\n<font color="grey">\n{reasoning_content_str}\n</font></details>'
            answer = f'{reasoning_content_formatted}\n\n------\n' + answer + '\n\n------\n'
        
        ai_alert_text = '<font color="red">内容由AI生成</font>' + '\n\n------\n'
              
        answer = f"{answer}{ai_alert_text}"

        print(f"==AI回答:>>:{answer}")
        print('================='*5)
        jq_queue.enqueue(f"DONE")
        if only_return_answer_text:
            return answer
        else:
            results = [self.code_text,answer]
            print(f"=========================最终结果=========================")
            print(results)
            print(f"=========================最终结果=========================")
            return results
                      
    # endregion: Graph定义            
        
tavily_search_tool = TavilySearchResults(max_results=6) #increased number of results

if __name__ == "__main__":
    user_questions = [
        "你是谁？请详细介绍一下你自己"
        "你装备了哪些工具？",
        "我现在的位置是在安徽晶奇网络科技股份有限公司附近，请查询15公里范围内的养老机构",
        "我现在的位置是在安徽晶奇网络科技股份有限公司附近，请查询15公里范围内的养老机构。并将查询到的养老机构名称（仅仅需要名称，不需要计算任何距离）通过python转换成excel文件，提供http的网络下载地址"
        "晶奇公司质量保证过程中的角色及角色的职责或含义解释，对应的人员（姓名）有哪些?其中的批准人是谁？",
        '你好，我的名字是张结魁，我是安徽晶奇网络科技股份有限公司的，请记住我的信息',
        '请搜索我与晶奇公司的相关网页，说明我与晶奇公司的关系',
        '晶奇公司的厦门市智慧民政一体化平台建设方案的编制依据，给出详尽的文件名称和文号等内容列表',
        '请绘制sin(x)曲线',
        '请生成波形变动的至少24个样例数据，绘制精美的，具有解释力的移动平滑平均曲线图，并能显示中文标题',
        '我公司是什么时候与西南石油大学建立校企合作关系的？',
        "晶奇公司编制的安徽省食品药品监督管理局行政审批系统项目总体计划的版本号是多少，批准人是谁？",
        '请搜索合肥大蜀山，然后提供详细介绍', 
        '请查询明天从合肥到上海的航班,以及南昌到北京的航班',
        '请直接执行代码：print("Hello World")',
        '请使用Python来绘制sin(x)的曲线图',        
        '合肥大蜀山',          
        '请查询明天从合肥到上海的航班',
        '请使用python_repl_tool来计算1到100的和',
        '请调用python_repl_tool工具，一个计算1到100的和,另一个计算10的阶乘，并实际执行工具获取计算结果',
        "请搜索网络然后回答问题：What is the weather in SF and LA? ",
        "Who won the super bowl in 2024? In what state is the winning team headquarters located?What is the GDP of that state? 最后请使用中文回答",
        "还记得我的名字吗？",
        """请将下面的内容：序号,文件名称,文号 1,《关于研究智慧民政和智慧市政建设工作的纪要》,厦门市人民政府专题会议纪要〔2020〕285号 2,《关于进一步推进儿童福利机构优化提质和创新转型高质量发展的意见》,民发〔2021〕44号 3,《民政部办公厅关于印发〈金民工程一期项目试点工作方案〉的通知》,民办函〔2019〕108号 4,《中共中央关于制定国民经济和社会发展第十四个五年规划和二〇三五年远景目标的建议》, 5,《国务院办公厅关于推进养老服务发展的意见》,国办发〔2019〕5号 6,《民政部关于进一步扩大养老服务供给促进养老服务消费的实施意见》,民发〔2019〕88号 7,《国务院扶贫开发领导小组关于建立防止返贫监测和帮扶机制的指导意见》,国开发〔2020〕6号 8,《国务院关于国家基本公共服务标准（2021年版 ）的批复》 , 国函 〔2021〕20号 9,《福建省促进电子证照应用管理暂行办法》,闽政办[2017]74号 10,厦门市人民政府办公厅关于进一步深化“互联网+政务服务”推进政务服务“一网、一门、一次”改革工作的通知,厦府办〔2018〕194号 11,《厦门市“十三五”民政事业发展专项规划（2016-2020）》, 12,厦门市城乡社区服务体系建设规划（2016-2020年）, 13,《关于加强和完善城乡社区治理的实施意见》,厦委发〔2018〕7号 \n
        转换为表格，使用python生成excel文件并提供http的网络下载地址""",
        '我现在的位置是在安徽晶奇网络科技股份有限公司附近，请查询15公里范围内的养老机构，最多返回10个',
        "全民健康信息平台包含的建设内容、系统或功能",
        "请检索知识库：医院信息系统",
        "请检索知识库回答，医院信息系统中的基础维护系统完整功能详述"
        "请搜索网络最新信息回答，安徽晶奇网络科技股份有限公司总部在哪个城市？该城市2024年的GDP是多少？"
    ]

    # user_questions = ['请调用工具函数帮我查询：我现在的位置是在安徽晶奇网络科技股份有限公司附近，请查询15公里范围内的养老机构，最多返回10个']
    # user_questions = ['我现在的位置是在安徽晶奇网络科技股份有限公司附近，请查询15公里范围内的养老机构，最多返回10个']
    # user_questions = ["请搜索网络然后回答问题：What is the weather in SF and LA?","Who won the super bowl in 2024? In what state is the winning team headquarters located?What is the GDP of that state? ","2024年安徽省会城市的GDP是多少? "]
    
    
    # user_questions=["晶奇公司质量保证过程中的角色及角色的职责或含义解释，对应的人员（姓名）有哪些?其中的批准人是谁？"]
    # user_questions += ["请检索知识库：安徽晶奇或晶奇网络相关的公司全称及英文名称"]
    
    # user_questions += ['请检索知识库，然后回答晶奇公司质量保证过程中的角色及角色的职责或含义解释，对应的人员（姓名）有哪些?其中的批准人是谁？']
    # user_questions += ["请检索知识库：信息"]
    # user_questions = ['ICD-10是什么？']
    my_main_bot = GraphAgent(executable_tools=executable_tools,routing_tools_wrapped_in_class=route_tools,allow_conversation_memory=True)

    # from fastapi import FastAPI
    # import threading
    # app = FastAPI()

    # from pydantic import BaseModel
    # from typing import List, Optional, Union

    # class JqChatRequest(BaseModel):
    #     question: Union[str, List[str]]
    # class JqChatResponse(BaseModel):
    #     answer: str


    # @app.post("/v1/jqchat", response_model=JqChatResponse)
    # def jqchat(request:JqChatRequest):
    #     answer = my_main_bot.run_conversation(user_question=request.question)
    #     logger.warning(f"FastAPI server answer：{answer}")
    #     return JqChatResponse(answer=answer)
    # def run_fastapi():
    #     import uvicorn
    #     uvicorn.run(app, host="0.0.0.0", port=8888)
    #     logger.warning("FastAPI server started at http://0.0.0.0:8888")

    # def test_jqchat_service(question:str="你好，请介绍一下你自己"):
    #     import requests
    #     url = f"http://10.1.150.105:8888/v1/jqchat"
        
    #     payload = {"question": question}
        
    #     response = requests.post(url, json=payload)
        
    #     if response.status_code == 200:
    #         print("Response from jqchat service:")
    #         print(response.json())
    #     else:
    #         print(f"Error: {response.status_code} - {response.answer}")

    #     return response.json()

    # import time
    # fastapi_thread = threading.Thread(target=run_fastapi)
    # fastapi_thread.start()
    # # fastapi_thread.join()
    # time.sleep(5)
    # # import multiprocessing
    # # fastapi_process = multiprocessing.Process(target=run_fastapi)
    # # fastapi_process.start()
    # # time.sleep(5)

    # response = test_jqchat_service()
    # print(response)
    # pass

    user_questions=['请绘制sin(x)曲线']
    for user_question in user_questions:
        if user_question == '请绘制sin(x)曲线':
            pass
        answer = my_main_bot.run_conversation(user_question=user_question)
        # response=test_jqchat_service(user_question)
        # print(f"{user_question}:\n{response}")
        pass


# source: https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components
