# source: https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components
# print('参考：https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components')
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Literal, Optional, Union, List
from langchain_core.pydantic_v1 import BaseModel, Field
# from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage,AIMessage
from langchain_core.tools import ToolException
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_openai import ChatOpenAI
from langchain import hub
from langchain.schema import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver
from langchain_core.runnables import Runnable, RunnableConfig
from jqcode.jq_agent.c0_init_env_models import env_models_instance,get_custom_handler,clean_up_list_when_encounter_null_element
from jqcode.jq_agent.tools.jq_functions_and_tools import get_flight_number,python_repl_tool
from langchain_experimental.tools import PythonREPLTool
from jqcode.jq_agent.tools.jq_retriever import get_retriever
import asyncio

# from jqcode.jq_agent.tools.jq_web_search_engine import get_web_search_documents,is_query_chinese,get_tavily_search_result_documents
from jqcode.jq_agent.tools.jq_web_search_engine_async import get_web_search_documents,is_query_chinese,get_tavily_search_result_documents
import os
import re
from jqcode.jq_code_executor.code_executor import CodeExecutorTool
import json_repair
import shortuuid
import uuid
from collections import deque
from flask import request, jsonify,Response
import requests
from jqcode.jq_utils.logger import jqkj_logger
from dotenv import load_dotenv
import time
_ = load_dotenv()
logger = jqkj_logger(__file__).get_logger()

python_repl = PythonREPLTool().run #这是原生的
# python_repl = python_repl_tool #这是我自己定义的，强制加入了print,已获取输出值
# python_repl = eval

DEBUG = False
handlers = get_custom_handler() if DEBUG else []
invoke_llm_config = {'callbacks' : handlers}    
# llm_model = env_models_instance.get_langchain_chat_model()
llm_model = env_models_instance.chat_model

class GraphAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    question : str
    question_related_messages: Annotated[list[AnyMessage], clean_up_list_when_encounter_null_element]
    question_searched : dict
    generation : str
    documents : List[str]


class LimitedLengthString:
    def __init__(self, maxlen=8000):
        self.data = deque()
        self.len = 0
        self.maxlen = maxlen

    def append(self, contents:Union[str,List[str],List[AnyMessage]]):
        if not isinstance(contents,list):
            contents = [contents]
        for content in contents:
            content = content.content if isinstance(content,AnyMessage) else content
            content = content.strip()
            if content:
                if content not in self.data:
                    self.data.append(content)
                    self.len += len(content)
                    while self.len > self.maxlen:
                        popped = self.data.popleft()
                        self.len -= len(popped)
                else:
                    logger.info(f"LimitedLengthString中已经存在'{content}'，忽略此次操作")        

    def get_string(self):
        result = '\n'.join(self.data)
        return result[-self.maxlen:]
    
message_buffer = LimitedLengthString()

# region: Router Data model Class Definitions
### Begin: Router Data model Class Definitions

question_rewrite_system_prompt = """结合上下文context部分考虑重写原始问题，使得原始问题更加明确全面，但要保留原始问题的本来意思或意图。
    如果原始问题中有不明确的实体指代,如该公司，他，这个地方等，请尽量用明确的实体内容来替换掉不明确的实体指代。
    如果不需要改写，请直接返回原始问题本身。
    仅仅需要返回问题内容本身，绝不能有任何额外的解释或内容。
    返回格式必须为Json:{"q":$question}，请使用改写后的问题内容替换$question
    """
question_rewrite_prompt = lambda x: ChatPromptTemplate.from_messages(
    [
        SystemMessage(question_rewrite_system_prompt),
        HumanMessage(
            f"'Context':\n{x['context']}\n'EndOfContext' \nQuestion: {x['question']} \nAnswer: "
        )
    ]
)
question_rewrite_chain = question_rewrite_prompt | llm_model

class WEB_SEARCH(BaseModel):
    """
    The internet. Use web_search for questions that are related to anything else than agent memory , prompt engineering, and adversarial attacks, 特别是2024年及以后相关的问题及发生的事情.
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
def web_search(state:GraphAgentState):
    """
    Web search based on the re-phrased question.

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Updates documents key with appended web results
    """

    print("---WEB SEARCH---")
    question = state["question"]
    try:
        query_generated = os.environ['rag_args']
        os.environ['rag_args'] = ''
        if os.environ['rag_args']:
            print(f"os.environ['rag_args']必须置为'',但现在的值为{os.environ['rag_args']} ")
            raise Exception
        if not query_generated:
            query_generated = llm_chain.invoke({"question": question,"context":'请生成合适并且简洁的搜索引擎查询关键词,不需要任何额外的解释或内容'},config=invoke_llm_config)
    except:
        query_generated = question
    print(f'{question=}')
    print(f'{query_generated=}')


    # Web search
    docs = asyncio.run(get_web_search_documents(query_generated,max_doc_nums=4))
    if not docs:
        return {"documents": [], "question_searched":{question:False}}
    
    if docs[0].metadata.get("search_engine",None)!="tavily_search":
        chunks_relevant = env_models_instance.split_and_get_chunks_relevant_from_documents(query=question,docs_list=docs,) #get embedding retriever and reranker results
    else:
       chunks_relevant = docs 
    referens = []
    filtered_source = []
    if chunks_relevant:
        _sources =[d.metadata.get("source",None) for d in chunks_relevant]
        sources = set([s for s in _sources if s])
        logger.info("相关的【网页标题】网址为:") 
               
        for s in sources:
            title = "TavilySearchResult无标题"
            for web_result in chunks_relevant:
                if s == web_result.metadata.get("source",None):
                    title = web_result.metadata.get("title","TavilySearchResult无标题")
                    filtered_source.append(web_result)
                    break
            print(f'【{title}】{s}')
            referens.append(s)
    if referens:
        referens_str = "   【参考网页为】:  \n"
        for i,r in enumerate(referens):
            # referens_str += f"    [{i+1}] <a href={r}>{r}</a>\n"
            referens_str += f"    {i+1}. [{r}]({r})  \n"
            
        os.environ["REFERENCE"] = referens_str
        print(f'{referens_str=}')
    else:
       os.environ["REFERENCE"] = '' 

    return {"documents": filtered_source, "question_searched":{question:True}}     



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
        Be sure to generate charts with plotly/matplotlib/seaborn, matplotlib.pyplot is preferred. But if you need geographical charts, use geopandas with the geopandas.datasets module.
        If the user has just uploaded a file, focus on the file that was most recently uploaded (and optionally all previously uploaded files)

        If the code modifies or produces a file/image, you must save the file/image to location '{env_models_instance.workspace}', and add a print statement at the end of the code block that prints a link to it as HTML string: <a href='/download?file=INSERT_FILENAME_HERE'>下载文件</a>. Replace INSERT_FILENAME_HERE with the actual filename.
    EndOf_GENERATE_PYTHON_INSTRUCTIONS
    """

usual_imports = """import numpy as np\nimport pandas as pd\nimport seaborn as sns\nimport matplotlib.pyplot as plt\nimport plotly.express as px\nimport plotly.graph_objects as go"""

usual_imports_list = usual_imports.split("\n")
usual_imports_list_striped = [line.strip() for line in usual_imports_list]
def merge_code_with_usual_imports(code:str,usual_imports_list=usual_imports_list_striped):
    code_lines = code.split("\n")
    code_lines_striped = [line.strip() for line in code_lines]

    code_lines_is_import = [code_line for code_line in code_lines_striped if code_line.startswith('import')] 
   
    for code_line in usual_imports_list_striped:
        if code_line not in code_lines_is_import:
            code_lines_striped.insert(0,code_line)

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

def submit_code_to_ipykernel_api(code:str):
    # KERNEL_API_BASE = os.getenv("KERNEL_API_BASE",'http://localhost')
    # API_PORT = os.getenv("API_PORT",5011)
    # kernel_api_url = f"{KERNEL_API_BASE}:{API_PORT}/api"
    kernel_api_url = env_models_instance.kernel_api_url
    # 故意制造错误，好测试本地执行的情况
    # kernel_api_url = env_models_instance.kernel_api_url + "error"
    requestjson = {'command':code}
    # /data/projects/JqChat/jqchat/kernel_program/main.py中的handle_request方法
    try:
        resp = requests.post(kernel_api_url, json=requestjson)
        result_dict = json_repair.loads(resp.content) #注意resp.content的类型为byte
        result = result_dict.get("result",None)
        if result=="success":
            logger.info("代码提交执行成功！")
            time.sleep(1)
            resp = requests.get(kernel_api_url)
            print(resp)
            return True
        else:
            logger.error("代码提交执行失败！")
            return False
    except Exception as e:
        logger.error(f"代码提交执行失败！错误信息为:{e}")
        return False
    
    try:
        resp = requests.get(kernel_api_url)
        print(resp)
        # results = [result_queue.get() for _ in range(result_queue.qsize())]
    except:
        pass

def display_code(code:str):
    _code = f"""python    
    ```
    {code}
    ```
    """
    return _code

# endregion: Some utils mothods or varaiables

    

# region: Rags Related
    
# 1. Coding Relavance Grader
class GradeCodingRelavance(BaseModel,extra='allow'):
    """Binary classification for a user question is relevant to [code generating/executing,file processing/analyzing, data exploring/analyzing]."""
    k: str = Field(description="Whether a user question is relevant to [code generating/executing,file processing/analyzing, data exploring/analyzing], k must be 'yes' or 'no'")

prompt_coding_relevant_grader = """You are a grader assessing relevance of a user question to [code generating/executing,file processing/analyzing, data exploring/analyzing]. Response me with a simple JSON string can be directly consumed by  ‘json.loads’ method, must be ‘{{"k":"yes"}}’ or  ‘{{"k":"no"}}’,'yes' means a user question is related to Python code generating/code executing.No preamble or explaination."""
structured_llm_coding_relevant_grader = llm_model.with_structured_output(GradeCodingRelavance,method='json_mode')
# structured_llm_coding_relevant_grader = llm_model.with_structured_output(GradeCodingRelavance)

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
structured_llm_documents_relevant_grader = llm_model.with_structured_output(GradeDocumentsRelavance,method='json_mode')
# structured_llm_documents_relevant_grader = llm_model.with_structured_output(GradeDocumentsRelavance)
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

    print("---CHECK DOCUMENT RELEVANCE TO QUESTION---")
    question = state["question"]
    documents = state["documents"]

    # Score each doc
    filtered_docs = []
    for d in documents:
        try:
            score = retrieval_document_relevance_grader.invoke({"question": question, "document": d.page_content},config=invoke_llm_config)
            grade = score.k
            if grade == "yes":
                print("---GRADE: DOCUMENT RELEVANT---")
                filtered_docs.append(d)
            else:
                print("---GRADE: DOCUMENT NOT RELEVANT---")
                continue
        except Exception as e:
            print(f"---ERROR: 无法获取'retrieval_document_relevance_grader'的判别结果，详细错误信息如下:---")
            print(e)
            filtered_docs.append(d)
    return {"documents": filtered_docs}
    # relevance_filtered_results = "\n".join([d.page_content for d in filtered_docs])
    # relevance_filtered_message = ToolMessage(content=relevance_filtered_results,name='grade_documents',tool_call_id='0')
    # return {"documents": filtered_docs, "question": question, "messages":relevance_filtered_message}

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
First, starting with "引用片段:  \n  ", find the quotes from the documents that are most relevant to answering the question, and then print them in numbered order. Each quote should be a relatively short summary sentence of the quoted document,and print in a seperated paragraph,by adding "  \n  ". 

If there are no relevant quotes, write “No relevant quotes” instead.

Then, answer the question, starting with "最终回答:  \n  ". Do not include or reference quoted content verbatim in the answer. Don’t say “According to Quote [1]” when answering. Instead make references to quotes relevant to each section of the answer solely by adding their bracketed reference numbers at the end of relevant quotes, If a section of the answer comes from multiple quotes, please list all applicable citations, like [1,2].

Thus, the format of your overall response should look like what’s shown between the tags. Make sure to strictly follow the formatting and spacing exactly.

引用片段:   \n  

    [1] Company X reported revenue of $12 million in 2021.   \n  
    [2] Almost 90% of revenue came from widget sales, with gadget sales making up the remaining 10%.   \n  

最终回答:   \n  

Company X earned $12 million[1].  Almost 90% of it was from widget sales[1,2]. 


If the question cannot be answered by the document, say so.

And you MUST answer the question, NEVER care about the year/time or tools/internet accessing limitations, Becuase you are provided enough tools/information/contexts to generate a resonable question.

Other than code and specific names and citations, your answer must be written in Simplified Chinese.

"""

def _gen_prompt_string(docs:List[Document]):
    prompt = ""
    for i,d in enumerate(docs):
        prompt += f"\n[{i+1}]:\n" + d.page_content
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

def generate(state:GraphAgentState):
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
    if not isinstance(documents, list):
      documents = [documents]
    # print("documents的内容：")
    # for d in documents:
    #     print(d.page_content)

    # RAG generation
    referens = []
    sources =[d.metadata.get("source",d.metadata.get("source",None)) for d in documents]
    # sources = set([s for s in _sources if s])
    referens = list(sources)

    referens_str = "参考'type_placeholder':  \n"
    if referens:        
        for i,r in enumerate(referens):
            referens_str += f"    {i+1}. [{r}]({r})  \n"
            if r.startswith("http"):
                referens_str = referens_str.replace("'type_placeholder'","网页")                
            else:
                referens_str = referens_str.replace("'type_placeholder'","文档")

        os.environ["REFERENCE"] = referens_str
        print(f'{referens_str=}')
    # else:
    #    os.environ["REFERENCE"] = '' 



    generation = rag_node.invoke({"documents": documents, "question": question, "messages":messages},config=invoke_llm_config)
    last_message = state["messages"][-1]
    tool_call_id = ''
    try:
        for tool_call in last_message.tool_calls:
            if tool_call["name"] == 'VECTORSTORE':
                tool_call_id = tool_call["id"]
                break
    except:
        tool_call_id = f'call_{str(uuid.uuid4())}'
    # print(generation)
    generation_message = ToolMessage(content=generation,name='generation',tool_call_id=tool_call_id)
    return {"documents": documents, "question": question, "generation": generation, "messages":generation_message,"question_related_messages":generation_message}




# 5.Supported (Not Hallucination) Grader
class GradeSupported(BaseModel,extra='allow'):  
    """Binary classification for whether an answer is supported by a set of facts."""
    k: str = Field(description="Whether answer is supported by the facts, k must be 'yes' or 'no'")

prompt_answer_is_supported_by_documents_grader = """You are a grader assessing whether an answer is supported by a set of facts. Response me with a simple JSON string can be directly consumed by  ‘json.loads’ method, must be ‘{{"k":"yes"}}’ or  ‘{{"k":"no"}}’,'yes' means the answer is supported by the provided set of facts.No preamble or explaination. """
structured_llm_answer_is_supported_by_documents_grader = llm_model.with_structured_output(GradeSupported,method='json_mode')
# structured_llm_answer_is_supported_by_documents_grader = llm_model.with_structured_output(GradeSupported)
answer_is_supported_by_documents_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompt_answer_is_supported_by_documents_grader),
        ("human", "Here are the set of facts: {documents} \n\n Here is the answer: {generation}"),
    ]
)
answer_is_supported_by_documents_grader = answer_is_supported_by_documents_prompt | structured_llm_answer_is_supported_by_documents_grader

class GradeAnswer(BaseModel,extra='allow'):
    """Binary classification to assess answer addresses question."""
    k: str = Field(description="Whether answer addresses the question, k must be 'yes' or 'no'")

prompt_answer_grader = """You are a grader assessing whether an answer addresses / resolves a question. Response me with a simple JSON string can be directly consumed by  ‘json.loads’ method, must be ‘{{"k":"yes"}}’ or  ‘{{"k":"no"}}’,'yes' means the answer addresses / resolves the question.No preamble or explaination."""
structured_llm_answer_grader = llm_model.with_structured_output(GradeAnswer,method='json_mode')
# structured_llm_answer_grader = llm_model.with_structured_output(GradeAnswer)
answer_prompt = ChatPromptTemplate.from_messages(
    [
        ("system",prompt_answer_grader),
        ("human", "question: {question} \n\nanswer: {generation}"),
    ]
)
answer_addresses_question_grader = answer_prompt | structured_llm_answer_grader

def grade_generation_v_documents_and_question(state:GraphAgentState):
    """
    Determines whether the generation is grounded in the document and answers question.

    Args:
        state (dict): The current graph state

    Returns:
        str: Decision for next node to call
    """

    print("---CHECK HALLUCINATIONS---")
    question = state["question"]
    documents = state["documents"]
    generation = state["generation"]

    # print(f"{len(documents[0].page_content)=}")

    # doc_num = len(documents)
    # token_len = int(2000/doc_num)
    # for i in range(doc_num):
    #     content = documents[i].page_content[-token_len:]
    #     documents[i].page_content = content
     
    # Check hallucination / answer_is_supported_by_documents    
    try:
        documents_contents = [d.page_content for d in documents]
        documents_contents_str = "\n".join(documents_contents)
        score = answer_is_supported_by_documents_grader.invoke({"documents": documents_contents_str, "generation": generation},config=invoke_llm_config)
        grade = score.k
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
            score = answer_addresses_question_grader.invoke({"question": question,"generation": generation},config=invoke_llm_config)
            grade = score.k
        except Exception as e:
            grade = "yes" # 继续按正常往下执行！
            print(f"---ERROR: 无法获取'answer_grader'的判别结果，详细错误信息如下:---")
            print(e)
            print("---正常往下执行---") 

        if grade == "yes":
            print("---DECISION: GENERATION ADDRESSES QUESTION---")
            return "useful"
        else:
            print("---DECISION: GENERATION DOES NOT ADDRESS QUESTION---")
            return "not useful"
            
            try:
                question_has_searched = state["question_searched"][question]
            except:
                question_has_searched = False
            
            if question_has_searched:
                print("---BUT WE HAVE WEB SEARCHED THE QUESTION, SO DIRECTLY ROUTE TO 'END' NODE---")
                return "useful"
            else:
                return "not useful"
    else:
        # pprint.pprint("---DECISION: GENERATION IS NOT GROUNDED IN DOCUMENTS, RE-TRY---")
        # return "not supported"
        print("---DECISION: GENERATION IS NOT GROUNDED IN DOCUMENTS, BUT WE DO NOT RE-TRY (RE-GENERATION), JUST DIRECTLY TO 'END' NODE---")
        return "not supported" # todo

# endregion Rags Related


    
    
executable_tools = [get_flight_number,python_repl_tool]
# executable_tools = [get_flight_number]
route_tools = [WEB_SEARCH,CODE_GENERATION,CODE_EXECUTION]

class GraphAgent:
    def __init__(self,executable_tools:list=executable_tools, routing_tools_wrapped_in_class:list=route_tools, llm_model:ChatOpenAI=None,chat_on_docs_list:List[str]=None,add_docs_list_to_kb:bool=True, kb_base_dict:dict={"name": 'zjk_jqesclient_test' , "discription":"A vectorstore/knowledge base containing documents related to 晶奇公司、安徽晶奇网络科技股份有限公司、医疗卫生、医疗健康、医疗服务、医疗政策、medical treatment & health. 凡是与晶奇公司、安徽晶奇网络科技股份有限公司及医疗健康相关的问题，都必须使用vectorstore工具。MUST use the vectorstore for questions on these topics."}, recursion_limit:int=25, memory_thread_id:str=shortuuid.uuid()) -> None:
        
    # region: 初始化
        # 获取知识库相关的信息
        self.kb_base_dict = kb_base_dict
        self.index_name = self.kb_base_dict.get("name",None)
        self.discription = self.kb_base_dict.get("discription",None)
        self.chat_on_docs_list = chat_on_docs_list
        self.add_docs_list_to_kb = add_docs_list_to_kb

        self.retriever = get_retriever(index_name=self.index_name,chat_on_docs_list=self.chat_on_docs_list,add_docs_list_to_kb=self.add_docs_list_to_kb,top_k=10,source_id_key='source',required_exts=['.doc','.docx','.pdf','.md'])

               
        self.VECTORSTORE.__doc__ = self.discription
        # 将self.VECTORSTORE加入
        # todo：这会导致重复加入很多个VECTORSTORE？
        routing_tools_wrapped_in_class+=[self.VECTORSTORE]

        _executable_tool_names = [tool.name for tool in executable_tools]        
        _routing_tool_names = [tool.__name__ for tool in routing_tools_wrapped_in_class]
        _tool_names = _executable_tool_names + _routing_tool_names
        _tool_names_str = ','.join(_tool_names)
        _system_message_content = f"Solve/Answer user's questions as best as you can in the language the user asked, preferred/default to Simplified Chinese. You have access to the following tools:{_tool_names_str}.You are allowed to make multiple calls (either together or in sequence).Choice Guidelines:First,'CODE_GENERATION' and 'CODE_EXECUTION' MUST NOT be called at the same time.Second, 'CODE_GENERATION' is preferred rather than 'python_repl_tool' for drawing images, plotting graphs/charts, data file processing/analyzing/saving, Otherwise, please use 'python_repl_tool'."

        if llm_model is None:
            llm_model = env_models_instance.get_langchain_chat_model()

        
        self.all_tools = executable_tools + routing_tools_wrapped_in_class
        self.all_tools_names = _tool_names
        self.routing_tool_names = _routing_tool_names
        self.executable_tool_names = _executable_tool_names
        self.executable_tool_dict = {t.name: t for t in executable_tools} 

        self.model = llm_model.bind_tools(self.all_tools)

        self.system_message = [SystemMessage(content=_system_message_content)]
        
        self.user_id = memory_thread_id
        self.question_id:str= self.get_random_id()
        self.question = ""
        self.question_rewrited = ""
        self.config =  {"recursion_limit":recursion_limit,"configurable": {"thread_id":memory_thread_id }}
        self.memory = SqliteSaver.from_conn_string("memory_checkpoints.sqlite")
        # self.memory = AsyncSqliteSaver.from_conn_string("memory_checkpoints.async_sqlite")
        
        self.message_idx_in_a_question_epoch = self.set_message_idx_in_a_question_epoch()
        self.graph = self.graph_definition()
        self.all_history_messages = self.get_all_history_messages()
        self.question_related_messages = self.get_question_related_messages_from_state()
    # endregion
    
    # region: 类内方法定义
    def makeup_message_with_question_id_idx(self,Message_ClassOrInstance:AnyMessage,content:Union[str,None]=None,question_id:Union[str,None]=None,idx_in_a_question_epoch:Union[int,None]=None):
        if not question_id:
            question_id = self.question_id
        if not idx_in_a_question_epoch:
            idx_in_a_question_epoch = self.set_message_idx_in_a_question_epoch()
        _dict = {"question_id":question_id,"idx_in_a_question_epoch":idx_in_a_question_epoch}
        if isinstance(Message_ClassOrInstance,AnyMessage):
            Message_ClassOrInstance.additional_kwargs.update(_dict)
            message = Message_ClassOrInstance
        else: 
            message = Message_ClassOrInstance(content=content,additional_kwargs=_dict)
        return message
    
    def get_question_id_idx_from_message(self,message:AnyMessage):
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
        
    def get_all_history_messages(self):
        self.all_history_messages = self._get_messages_from_state_by_key("messages") 
        return self.all_history_messages
    
    def get_question_related_messages_from_state(self,question="",reserve_last_n_unique_messages=6):
        self.question_related_messages = self._get_messages_from_state_by_key("question_related_messages")

        if not self.question_related_messages:
            messages = self.get_all_history_messages() ## 或者  messages = state['messages']
            if messages:
                if len(messages) == 1:
                    self.question_related_messages = messages
                else:
                    question = question or self.question_rewrited
                    if not question:
                        logger.warning('请传入非空的user question，或者先给self.question_rewrited赋值')
                    else:
                        question_related_messages = env_models_instance.filter_and_get_messages_relevant_to_query(query=question,messages_list=messages,reserve_last_n_unique_messages = reserve_last_n_unique_messages)
                        self.question_related_messages = question_related_messages

        return self.question_related_messages

    def _get_messages_from_state_by_key(self,key:str):
        messages = self.graph.get_state(config=self.config).values[key] 
        return messages
    
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

        # Retrieval
        documents = self.retriever.invoke(question,config=invoke_llm_config)
        # retrieve_results = "\n".join([d["content"] for d in documents])
        # 因为retrieve_results必去grade_documents节点过滤[workflow.add_edge("retrieve", "grade_documents")]，
        # 所以此次不添加retrieve_message，而是到grade_documents节点，仅保留过滤后的
        # retrieve_message = ToolMessage(content=retrieve_results,name='retrieve')
        # return {"documents": documents, "question": question,"messages":retrieve_message}
        return {"documents": documents, "question": question}

    # endregion 类内方法  
    
    # region:Graph定义
    def graph_definition(self,):
        graph = StateGraph(GraphAgentState)
        graph.add_node("llm",self.call_llm)
        graph.add_node("action", self.take_action)
        graph.add_node("web_search", web_search)
        graph.add_node("vectorstore", self.vectorstore )
        graph.add_node("grade_documents", grade_documents )
        graph.add_node("generate", generate)
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
            grade_generation_v_documents_and_question,
            {
                # "not supported": "generate", # Hallucinations: re-generate 
                "not supported": END, # todo
                "not useful": "web_search", # Fails to answer question: fall-back to web-search 
                "useful": END,
            },
        )
        
        return graph.compile(checkpointer=self.memory)
    
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
                # return {'messages': results,'question_related_messages':results}   
            

        logger.info("工具调用执行正常，返回到大模型")
        return {'messages': results,'question_related_messages':results}
    
    def exists_action(self,state:GraphAgentState):
        
        result = state['messages'][-1]
        print("xxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        print(f'{result.content=}')
        print("xxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        finish_reason = "No Finish Reason"
        try:
            returned_tool_calling_nums = len(result.tool_calls)
            finish_reason = result.response_metadata["finish_reason"]
        except:
            returned_tool_calling_nums = 0

        if returned_tool_calling_nums==0 and self.model.model_name.startswith(("qwen","deepseek")):
            if self.model.model_name.startswith("qwen"):
                arg_name = "arguments" 
            elif self.model.model_name.startswith("deepseek"):
                arg_name = "parameters"
            else:
                arg_name = "parameters" 
            try:
                tool_calls = []
                tool_calls_json_list = json_repair.loads(result.content)
                if isinstance(tool_calls_json_list,dict):
                    tool_calls_json_list = [tool_calls_json_list]
                for tool_call in tool_calls_json_list:
                    tool_name = tool_call['name']
                    if tool_name in ["directly-answer","directly_answer"]:
                        result.tool_calls = []
                        break
                    else:
                        if tool_name in self.all_tools_names:
                            parameters = tool_call[arg_name]
                            if not isinstance(parameters,dict):
                                parameters = json_repair.loads(parameters)
                            tool_calls.append({"name":tool_name,"args":parameters,"id":f'call_{str(uuid.uuid4())}'})
                result.tool_calls = tool_calls
                returned_tool_calling_nums = len(result.tool_calls)
            except:
                logger.debug(f"Can't parser tool calls from models response content")


        if returned_tool_calling_nums > 0:
            logger.debug(f'Returned {returned_tool_calling_nums} tool_calls')
            if returned_tool_calling_nums>1:
                logger.info(f'!!! 惊喜: Multitple({returned_tool_calling_nums=}) tool_calls !!!')
            
            tool_call_1 = result.tool_calls[0]
            tool_call_1_name = tool_call_1['name']
            if tool_call_1_name in self.routing_tool_names:
                logger.info(f"Returned first ToolName is '{tool_call_1_name}', So routing to '{tool_call_1_name}' Node......")
                # 有些模型会同时生成多个调用（如deep seek），但又要求tool_call与tool_response必须对应起来，所以此处只好生成一一对应的tool_response message
                for tool in result.tool_calls[1:]:
                    makeup_tool_message = ToolMessage(content='',name=tool["name"],tool_call_id=tool["id"])
                    messages = state["messages"]
                    messages.append(makeup_tool_message)  
                    state.update({"messages":messages})
                    # state["messages"]=state["messages"].append(makeup_tool_message)                  
                return tool_call_1_name
            
        else:
            logger.info(f'No returned tool_calling and {finish_reason=}')
            logger.info(f'{result.type.upper()}: {result.content}')            
        exists_action_or_not = True if returned_tool_calling_nums>0 else False
        return exists_action_or_not
    
    def code_execution_passed(self,state:GraphAgentState):
        status = False
        last_message = state['question_related_messages'][-1]
        if isinstance(last_message,ToolMessage):
            if last_message.name.lower() == 'code_execution':
                status = last_message.additional_kwargs.get("status",False)
        return "end" if status else "llm"

    def call_llm(self,state: GraphAgentState):
        # 当前message
        input_message = state.get('messages')[-1]
        # 获取历史相关message
        question_related_messages = self.get_question_related_messages_from_state()
        assert self.question_related_messages == question_related_messages,"self.get_question_related_messages_from_state方法里应同步更新了self.question_related_messages"        
        # 历史 + 当前
        if input_message not in question_related_messages:
            question_related_messages.append(input_message)
        if self.system_message:
            messages = self.system_message + question_related_messages
            
        logger.info(f"call_llm:调用LLM时的消息数为:{len(messages)}")
        
        # 为了保证在线模型要求的tool_call AIMessage 和 tool_response ToolMessage要求的一一对应，且tool_call_id要匹配的上，所以此处把含有tool_call的AIMessage过滤掉
        # filtered_messages = []
        # for _m in self.question_related_messages:
        #     if isinstance(_m,HumanMessage):
        #         filtered_messages.append(_m)
        #     if isinstance(_m,AIMessage):
        #         tool_calls = _m.tool_calls
        #         if len(tool_calls) == 0:
        #             filtered_messages.append(_m)
                    
        # self.question_related_messages = filtered_messages
        message = None
        try:
            try:
                # 为了保证在线模型要求的tool_call AIMessage 和 tool_response ToolMessage要求的一一对应，且tool_call_id要匹配的上
                tool_messages = [t for t in messages if isinstance(t,ToolMessage)]
                tool_response_ids = [t.tool_call_id for t in tool_messages]
                ai_messages_with_tool_calls = [t for t in messages if isinstance(t,AIMessage) and len(t.tool_calls)>0]
                tool_call_ids = []
                ai_messages_with_tool_calls_but_has_no_crospongding_tool_message = []
                tool_messages_but_has_no_crospongding_ai_message = []
                for t in ai_messages_with_tool_calls:
                    ts = t.tool_calls
                    for _t in ts:
                        if _t["id"] not in tool_response_ids:
                            ai_messages_with_tool_calls_but_has_no_crospongding_tool_message.append(_t)
                        else:
                            tool_call_ids.append(_t["id"])
                for t in tool_messages:
                    if t.tool_call_id not in tool_call_ids:
                        tool_messages_but_has_no_crospongding_ai_message.append(t)
                
                invalid_messages = tool_messages_but_has_no_crospongding_ai_message + tool_messages_but_has_no_crospongding_ai_message
                filtered_messages = [m for m in messages if m not in invalid_messages] 
                if len(filtered_messages)!=len(messages):
                    logger.debug('有不匹配的ai_messages_with_tool_calls_but_has_no_crospongding_tool_message或tool_messages_but_has_no_crospongding_ai_message过滤掉了')          

                message = self.model.invoke(filtered_messages,config=self.config)
            except Exception as e:
                print(f"{filtered_messages},{e}")
                # message = self.model.invoke(filtered_messages,config=self.config)
            if message:
                try: 
                    finish_reason = message.response_metadata["finish_reason"]
                    if finish_reason ==  "length":
                        reason = 'a finish_reason of “length” means that the AI had more data to output but the limitations of that call prevented it from finishing'
                        model_name = self.model.bound.model_name
                        max_tokens = self.model.bound.max_tokens
                        logger.warning(f'LLM({model_name})返回: finish_reason ==  "length" [{reason}]，当前设置的max_tokens={max_tokens}，请检查调整该设置')
                        print(f'LLM({model_name})返回: finish_reason ==  "length" [{reason}]，当前设置的max_tokens={max_tokens}，请检查调整该设置值!')
                except Exception as e:
                    logger.error("无法获取到finish_reason，错误消息为：{e}")
                    message.pretty_print()

                message = self.makeup_message_with_question_id_idx(message)
                question_related_messages.append(message)
                return {'messages': message,'question_related_messages':question_related_messages}
        except Exception as e:
            logger.error(f'！！！大语言模型执行失败，！！！错误消息为:{e}')
            # logger.error('请检查大语言模型接口服务状态,并查看传入的消息列表，如下：')            
            # for m in messages:
            #     m.pretty_print()
    
    def code_generation(self,state:GraphAgentState):
        user_question = state["question"]
        last_message = state["messages"][-1]
        question_related_messages = state["question_related_messages"]
        message_buffer.append(question_related_messages)

        user_code_prompt = f"""First, here is a history of what I asked you to do earlier. 
        The actual user prompt follows after ENDOFHISTORY. 
        History:
        {message_buffer.get_string()}
        ENDOFHISTORY.
        Aiming to help the user in the best possible way with the below [USER_QUESTION] do one of the following:
        1. Write Python code, in a triple backtick Markdown code block, that supports what the user is trying to achieve. Follows the system instructions between [GENERATE_PYTHON_INSTRUCTIONS] and [EndOf_GENERATE_PYTHON_INSTRUCTIONS]
        2. Answer the question the user asks.
        3. Ask follow-up questions to better understand what the user wants to achieve. 
        
        [USER_QUESTION]
        {user_question}
        """

        sys_message = SystemMessage(content=system_code_prompt)
        human_message = HumanMessage(content=user_code_prompt)
        code,code_text = "",""
        try:
            code_generated = llm_model.invoke([sys_message,human_message])
            code_text = code_generated.content.strip()        
            code = extract_code(code_text)
        except Exception as e:
            logger.warning(f"请求code_generation时出现错误:{e}")
        
        if code:
            logger.info('生成、抽取到的代码为：\n' + code)
            code = merge_code_with_usual_imports(code) # 加入常用的imports，防止代码生成中出现的遗漏错误
        tool_call_id = ''
        try:
            for tool_call in last_message.tool_calls:
                if tool_call["name"] == 'CODE_GENERATION':
                    tool_call_id = tool_call["id"]
                    break
        except:
            tool_call_id = f'call_{str(uuid.uuid4())}'
        
        code_message = ToolMessage(content=code,name='code_generation',tool_call_id = tool_call_id,additional_kwargs ={"code_text":code_text})
        code_message = self.makeup_message_with_question_id_idx(code_message)
        # 在线大模型服务要求tool_call aimessage 与 tool_response toolmessage要一一对应，所以这里要先生成一个tool_call aimessage
        code_execution_tool_call_message = AIMessage(name="code_generation",content='',tool_calls=[{"name":"CODE_EXECUTION","args":{"query":code},"id":f'call_{(shortuuid.uuid())}'}])
        code_execution_tool_call_message = self.makeup_message_with_question_id_idx(code_execution_tool_call_message)
        messages = [code_message,code_execution_tool_call_message]
        return {'messages':messages,'question_related_messages':messages}

    def code_execution(self,state:GraphAgentState):
        question =  state["question"]
        question_related_messages = state["question_related_messages"]
        last_message = question_related_messages[-1]
        question_id = last_message.additional_kwargs.get('question_id','')

        try:
            for tool_call in last_message.tool_calls:
                if tool_call["name"] == 'CODE_EXECUTION':
                    tool_call_id = tool_call["id"]
                    break
        except:
            tool_call_id = f'call_{str(uuid.uuid4())}'
        tool_name = 'code_execution'
        code_executor=CodeExecutorTool()
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
                message_content += code_text
                logger.debug("......开始提交和执行代码......") 
                # 提交代码到ipykernel_api执行   
                # result = submit_code_to_ipykernel_api(code) #返回True或False
                # 返回值为{"text"="",image=""}
                result=code_executor.call(code=code)
                if result:               
                    message_content+=result['image']
                    message_content+=result['text']
                    logger.debug("......代码执行完毕......")
                # 提交代码到ipykernel_api执行，尝试本地来执行
                # 不应该需要本地执行
                if not result:
                    logger.info(f"......提交和执行代码失败，请检查服务接口......")
                    logger.info(f".......尝试使用本地的python环境来来执行.......")
                    # python_repl在本页代码开头处赋值的 
                    result = python_repl(code)

                                    
                    if "error" in result.lower():
                        code = merge_code_with_usual_imports(code)
                        # python_repl在本页代码开头处赋值的  
                        result = python_repl(code)                                      
                        if "error" in result.lower():
                            raise Exception(result)
                    else:
                        _result = result if result else "None"
                        message_content = f"python_repl代码运行成功,运行结果为Observation:{_result} （但如有图像，由于环境限制无法直接展示,可在本地环境中运行上述代码）"
                
                code_message = ToolMessage(content=message_content,name=tool_name,tool_call_id =tool_call_id,additional_kwargs ={"status":False,"code":code,"code_text":code_text})
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
        
    def run_conversation(self,user_question:str,allow_question_rewrite=False):
        print('================='*5)
        print('================='*5)
        print(f"开始会话:{user_question}")
        print('================='*5)
        # logger.info(f"老的{self.question_id=}")
        logger.debug(f"切记新的问题对话前，要先更新user_question 和 question_id！老的[{self.question_id=}]")
        self.question_id = self.get_random_id()
        self.question = user_question #因为涉及获取question相关的历史消息，以及根据question相关的历史消息改写question（rewrite），放到self.question供调用
        self.question_related_messages = self.get_question_related_messages_from_state(user_question,reserve_last_n_unique_messages=6)
        
        logger.warning("此处要默认不改写问题，但实际需要获取用户是否运行改写的设置")
                
        self.question_rewrited = user_question #后面会使用self.question_rewrited提交给大模型，就要确保self.question_rewrited有值
        if allow_question_rewrite:
            if self.question_related_messages:
                question_rewrited = ''            
                rewrite_message_returned = None
                # 尝试获取question_rewrited 
                try:
                    context = "\n".join([m.content for m in self.question_related_messages if m.content])
                    rewrite_message_returned = question_rewrite_chain.invoke({'context':context,'question':user_question})
                    json_content = json_repair.loads(rewrite_message_returned.content)
                    if json_content:
                        question_rewrited = json_content.get("q","")                
                except Exception as e:
                    logger.warning(f"尝试进行问题改写失败，错误消息为:{e}")
                    if rewrite_message_returned:
                        logger.info("======下面是大模型返回的消息内容======")
                        rewrite_message_returned.pretty_print()
                    else:
                        logger.info("======大模型未能返回消息======")
                # 处理question_rewrited 
                if question_rewrited:
                    if question_rewrited != self.question_rewrited:
                        logger.warning(f"进行了问题改写:{self.question_rewrited} => {question_rewrited}")
                        self.question_rewrited = question_rewrited ##仅在问题内容变化后，才赋值给self.question_rewrited，改写前已设置self.question_rewrited = user_question

        logger.debug(f"USER[id:{self.user_id}]的问题['{self.question_rewrited}'] (新的question_id: [{self.question_id})]")
        input_message = self.makeup_message_with_question_id_idx(HumanMessage,content=self.question_rewrited)       
        result = self.graph.invoke({"messages": [input_message],"question":self.question_rewrited,"question_related_messages":[]},config=self.config)
        
        logger.debug(f"==USER[id:{self.user_id}]的问题[id:{self.question_id}]，允许问题改写:{allow_question_rewrite}")
        print(f'====问题和答案====')        
        print(f"原始问题>>:{user_question}")
        print(f"改写问题>>:{self.question_rewrited} [{allow_question_rewrite=}]")
        answer = result['messages'][-1].content
        referens_str = os.getenv("REFERENCE", '')
        os.environ["REFERENCE"]= ''
        if referens_str:
            answer = f'\n{referens_str}\n' + answer
        print(f"==AI回答:>>:{answer}")
        print('================='*5)
        return answer
    # endregion: Graph定义            
        
        



tavily_search_tool = TavilySearchResults(max_results=4) #increased number of results

# 




if __name__ == "__main__":
    user_questions = [
        '请绘制sin(x)曲线',
        "安徽省食品药品监督管理局行政审批系统项目总体计划的版本号是多少，批准人是谁？",
        '请搜索合肥大蜀山，然后提供详细介绍', 
        '请查询明天从合肥到上海的航班,以及南昌到北京的航班',
        '请直接执行代码：print("直接执行打印程序代码")',
        '请使用Python来绘制sin(x)的曲线图',
        '你好，我叫张结魁',
        '合肥大蜀山',          
        '请查询明天从合肥到上海的航班',
        '请使用python_repl_tool来计算1到100的和',
        '请调用python_repl_tool工具，一个计算1到100的和,另一个计算10的阶乘，并实际执行工具获取计算结果',
        "请搜索网络然后回答问题：What is the weather in SF and LA? ",
        "Who won the super bowl in 2024? In what state is the winning team headquarters located?What is the GDP of that state? ",
        "还记得我叫什么吗？"
    ]
    my_main_bot = GraphAgent(executable_tools=executable_tools,routing_tools_wrapped_in_class=route_tools)

    for user_question in user_questions:
        answer = my_main_bot.run_conversation(user_question=user_question)


# source: https://learn.deeplearning.ai/courses/ai-agents-in-langgraph/lesson/3/langgraph-components    