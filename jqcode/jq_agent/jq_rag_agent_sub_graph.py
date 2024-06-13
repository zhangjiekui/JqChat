# https://langchain-ai.github.io/langgraph/tutorials/introduction/
# https://github.com/langchain-ai/langgraph/blob/main/examples/persistence.ipynb
import re
import asyncio
import pprint
from langchain.schema import Document
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver
from typing import Annotated, List
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langgraph.pregel import GraphRecursionError
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage,SystemMessage,ToolMessage,AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.tools.tavily_search import TavilySearchResults ### Search
# from langchain_community.chat_models import ChatOllama
from jqcode.jq_agent.c0_init_env_models import get_langchain_chat_model,get_langchain_chat_ollama_functions,USING_OLLAMA_FUNCTIONS,USING_OLLAMA_LITELLM
from jqcode.jq_agent.c0_init_env_models import get_emb_8k_rerank_model
from jqcode.jq_agent.c0_init_env_models import get_es_connection, get_es_searchstore, get_es_searchstore_index_documents
from jqcode.jq_agent.tools.jq_web_search_engine import get_web_search_documents,is_query_chinese
from copy import deepcopy
from jqcode.jq_agent.graph_create_utils import create_graph_supervisor, create_agent, agent_node, sub_graph_enter_chain
from jqcode.jq_agent.tools.jq_functions_and_tools import primary_tool_assistant_prompt, excutable_tool_node, excutable_tools,excutable_tool_names
from jqcode.jq_agent.tools.jq_retriever import retriever
from jqcode.jq_agent.graph_create_utils import supervisor_post_process_node,get_last_state, get_custom_supervisor_node,llm
from langchain_core.runnables import Runnable,RunnablePassthrough,RunnableLambda
from typing import Annotated, List, TypedDict
from langgraph.graph import END, StateGraph
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
import functools

### GraphState
class RagSubgraphState(TypedDict):
    """|
    Represents the state of our graph.

    Attributes:
        # question: question
        generation: LLM generation
        documents: list of documents
        question_searched : dict
        messages: Annotated[list, add_messages]
    """
    team_members: List[str]
    next: str
    tool_members: List[str]
    question : str
    generation : str
    documents : List[str]
    question_searched : dict
    messages: Annotated[list, add_messages]
        # Messages have the type "list". 
        # The `add_messages` function in the annotation defines how this state key should be updated
        # (in this case, it appends messages to the list, rather than overwriting them)


### Router Data model
class direct_response(BaseModel):
    """
    Direct response. Answer user directly if you do know how to response.
    """
    query: str = Field(description="The question user want you to answer.")

class web_search(BaseModel):
    """
    The internet. Use web_search for questions that are related to anything else than agent memory , prompt engineering, and adversarial attacks.
    """
    query: str = Field(description="The query to use when searching the internet.")

class vectorstore(BaseModel):
    """
    A vectorstore containing documents related to 医疗卫生、医疗健康、医疗服务、医疗政策、medical treatment & health. 凡是与医疗健康相关的问题，都必须使用vectorstore工具。MUST use the vectorstore for questions on these topics.
    """
    query: str = Field(description="The query to use when searching the vectorstore.")

class code_generation(BaseModel):
    """
    Code Assistant/Code generation . Use programming code (preferred Python language) to slove a user question, if the question related to [code generating, file processing/analyzing, data exploring/analyzing/visualizing].
    """
    query: str = Field(description="The query to use when generating code.")

class code_execution(BaseModel):
    """
    Code execution/Code intepreter. When user providing a code snippet and asking for running/executing, w or w/o returning the result.
    """
    query: str = Field(description="The query to use when asking for running/executing a code snippet.")

members  = ["web_search", "vectorstore", "code_generation", "code_execution", "direct_response"]
tools=[web_search, vectorstore, code_generation, code_execution, direct_response]
excutable_tool_names = ["web_search", "vectorstore", "code_generation", "code_execution", "direct_response"]
supervisor_agent = create_graph_supervisor(
    llm,
    " You are a supervisor tasked with managing a conversation between the"
    " following tools:  get_flight_number,python_repl_tool.  Given the following user request,"
    " respond with the tool to act next. Each tool will perform a specific task and respond with their results and status. When finished, respond with FINISH.",
    excutable_tool_names,
)


# Preamble
if USING_OLLAMA_FUNCTIONS:
    # tools.append(direct_response)
    tool_names=", ".join([str(tool).split('__.')[-1][:-2] for tool in tools])
    structured_llm_router = llm.bind_tools(tools=tools)     
else:
    structured_llm_router = llm.bind_tools(tools=tools) 
    tool_names=", ".join([tool['function']['name'] for tool in structured_llm_router.kwargs['tools']])
    
print(tool_names)
member_names =", ".join(members)
print(member_names)
# preamble_llm_router = """You are an expert at answer the user's question: (1)answer user directly if you do know how to response; (2)routing to 'tool_assistant' to get flight number, write and execute python code to answer questions; or (3)routing the user question to a tool if you don't know how to answer the questions. You have access to the following tools: """ + tool_names 
preamble_llm_router = f"""You are a master, you are equipped with various tools can: search web, retrieve documnets vectorstore, execute code......,  Response to user's question by calling one or more tools among of the following tools: {tool_names}. """   
# print(preamble_llm_router)

# Prompt
route_prompt = ChatPromptTemplate.from_messages(
    [
        ("system",preamble_llm_router),
        ("human", "{question}"),
    ]
)

question_router = route_prompt | structured_llm_router

llm_for_excutable_tools = llm.bind_tools(tools=excutable_tools)
tool_router = route_prompt | llm_for_excutable_tools
# res2 = question_router.invoke("请使用python生成代码，绘制和保存y=sin(x)的曲线图，并实际运行/执行代码，提供下载链接")
# print(res2)


### Coding Grader
# Coding Grader Data model
class GradeCodingRelavance(BaseModel):
    """Binary classification for a user question is relevant to code generating/code executing."""
    k: str = Field(description="Whether a user question is relevant to [code generating/executing,file processing/analyzing, data exploring/analyzing], k must be 'yes' or 'no'")
# Code Generating/Code Executing Relavance Grader Prompt
preamble_coding_relevant_grader = """You are a grader assessing relevance of a user question to [code generating/executing,file processing/analyzing, data exploring/analyzing]. Response me with a simple JSON string can be directly consumed by  ‘json.loads’ method, must be ‘{{"k":"yes"}}’ or  ‘{{"k":"no"}}’,'yes' means a user question is related to Python code generating/code executing.No preamble or explaination."""
# structured_llm_documents_relevant_grader = llm.with_structured_output(GradeDocumentsRelavance, method=method_mode, include_raw=True)
method_mode ='function_calling' if USING_OLLAMA_LITELLM else "json_mode"
if USING_OLLAMA_FUNCTIONS:
    structured_llm_coding_relevant_grader = llm.with_structured_output(GradeCodingRelavance)
else:
    structured_llm_coding_relevant_grader = llm.with_structured_output(GradeCodingRelavance,method=method_mode)


coding_relevance_prompt = ChatPromptTemplate.from_messages(
    [
        ("system",preamble_coding_relevant_grader),
        # SystemMessage(preamble_documents_relevant_grader), #就可以在提示语中不必使用‘{{"k":"yes"}}’
        ("human", "User question: {question}")
    ]
)
# Coding Relavance Grader
coding_relevance_grader = coding_relevance_prompt | structured_llm_coding_relevant_grader


### Retrieval Grader

# Retrieval Grader Data model
class GradeDocumentsRelavance(BaseModel):
    """Binary classification for relevance check on retrieved documents."""
    k: str = Field(description="Whether Documents are relevant to the question, k must be 'yes' or 'no'")

# Retrieval Documents Relavance Grader Prompt
preamble_documents_relevant_grader = """You are a grader assessing relevance of a retrieved document to a user question. If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant. It does not need to be a stringent test.The goal is to filter out erroneous retrievals. Response me with a simple JSON string can be directly consumed by  ‘json.loads’ method, must be ‘{{"k":"yes"}}’ or  ‘{{"k":"no"}}’,'yes' means a retrieved document is related to a user question.No preamble or explaination."""
# structured_llm_documents_relevant_grader = llm.with_structured_output(GradeDocumentsRelavance, method=method_mode, include_raw=True)

if USING_OLLAMA_FUNCTIONS:
    structured_llm_documents_relevant_grader = llm.with_structured_output(GradeDocumentsRelavance)
else:
    structured_llm_documents_relevant_grader = llm.with_structured_output(GradeDocumentsRelavance,method=method_mode)

retrieval_document_relevance_prompt = ChatPromptTemplate.from_messages(
    [
        ("system",preamble_documents_relevant_grader),
        # SystemMessage(preamble_documents_relevant_grader), #就可以在提示语中不必使用‘{{"k":"yes"}}’
        ("human", "Retrieved document: {document} \n\n User question: {question}")
    ]
)
# Retrieval Documents Relavance Grader
retrieval_document_relevance_grader = retrieval_document_relevance_prompt | structured_llm_documents_relevant_grader

### RAG Generate
# Preamble
preamble_rag = """You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, just say that you don't know. Use three sentences maximum and keep the answer concise."""

# Prompt
prompt = lambda x: ChatPromptTemplate.from_messages(
    [
        SystemMessage(preamble_rag),
        HumanMessage(
            f"Question: {x['question']} \nAnswer: ",
            additional_kwargs={"documents": x["documents"]},
        )
    ]
)

# RAG Chain
rag_node = prompt | llm | StrOutputParser()

### LLM Generate/Fallback
# Preamble
preamble_llm = """You are an assistant for question-answering tasks. Answer the question based upon your knowledge in the language the user asked ."""
# Prompt
prompt = lambda x: ChatPromptTemplate.from_messages(
    [
        SystemMessage(preamble_llm),
        HumanMessage(
            f"'Context':\n{x['context']}\n'EndOfContext' \nQuestion: {x['question']} \nAnswer: "
        )
    ]
)

# LLM Chain
llm_chain = prompt | llm | StrOutputParser()


### Supported Grader

# Supported Grader Data model
class GradeSupported(BaseModel):
    """Binary classification for whether an answer is supported by a set of facts."""
    k: str = Field(description="Whether answer is supported by the facts, k must be 'yes' or 'no'")

#Supported Grader Preamble

preamble_answer_is_supported_by_documents_grader = """You are a grader assessing whether an answer is supported by a set of facts. Response me with a simple JSON string can be directly consumed by  ‘json.loads’ method, must be ‘{{"k":"yes"}}’ or  ‘{{"k":"no"}}’,'yes' means the answer is supported by the provided set of facts.No preamble or explaination. """
if USING_OLLAMA_FUNCTIONS:
    structured_llm_answer_is_supported_by_documents_grader = llm.with_structured_output(GradeSupported)
else:
    structured_llm_answer_is_supported_by_documents_grader = llm.with_structured_output(GradeSupported, method=method_mode)
# Supported (Hallucination) Grader Prompt
answer_is_supported_by_documents_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", preamble_answer_is_supported_by_documents_grader),
        ("human", "Here are the set of facts: {documents} \n\n Here is the answer: {generation}"),
    ]
)
# Supported (Hallucination) Grader
answer_is_supported_by_documents_grader = answer_is_supported_by_documents_prompt | structured_llm_answer_is_supported_by_documents_grader


### Answer Grader

# Data model
class GradeAnswer(BaseModel):
    """Binary classification to assess answer addresses question."""
    k: str = Field(description="Whether answer addresses the question, k must be 'yes' or 'no'")

# Preamble
preamble_answer_grader = """You are a grader assessing whether an answer addresses / resolves a question. Response me with a simple JSON string can be directly consumed by  ‘json.loads’ method, must be ‘{{"k":"yes"}}’ or  ‘{{"k":"no"}}’,'yes' means the answer addresses / resolves the question.No preamble or explaination."""
if USING_OLLAMA_FUNCTIONS:
    structured_llm_answer_grader = llm.with_structured_output(GradeAnswer)
else:
    structured_llm_answer_grader = llm.with_structured_output(GradeAnswer, method=method_mode)

# Prompt
answer_prompt = ChatPromptTemplate.from_messages(
    [
        ("system",preamble_answer_grader),
        ("human", "question: {question} \n\n answer: {generation}"),
    ]
)
# answer grader
answer_grader = answer_prompt | structured_llm_answer_grader



## Graph nodes definition

def retrieve(state:RagSubgraphState):
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
    documents = retriever.invoke(question)
    # retrieve_results = "\n".join([d["content"] for d in documents])
    # 因为retrieve_results必去grade_documents节点过滤[workflow.add_edge("retrieve", "grade_documents")]，
    # 所以此次不添加retrieve_message，而是到grade_documents节点，仅保留过滤后的
    # retrieve_message = ToolMessage(content=retrieve_results,name='retrieve')
    # return {"documents": documents, "question": question,"messages":retrieve_message}
    return {"documents": documents, "question": question}

def llm_fallback(state:RagSubgraphState):
    """
    Generate answer using the LLM w/o vectorstore

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): New key added to state, generation, that contains LLM generation
    """
    print("---LLM Fallback---")
    question = state["question"]
    # messages_content = [f'[{m.type}]{";".join([m.tool_call["name"] for tool_call in m.tool_calls]) if hasattr(m,"tool_calls") and m.tool_calls else m.content}' for m in state["messages"]]
    
    messages_content = []
    for m in state["messages"]:
        _str = f'[{m.type}]'
        if isinstance(m,AIMessage):
            if len(m.tool_calls)>0:
                _tools = "、".join([tool_call["name"] for tool_call in m.tool_calls])
                _str+=f"Using Tools:{_tools}"
            else:
                content = m.content
                _str+=content
        else:
            content = m.content
            _str+=content
        # print(_str)
        messages_content.append(_str)
    
    messages_content_without_repeated = sorted(set(messages_content),key=messages_content.index)                        
    context_str = ';'.join(messages_content_without_repeated)
    print(f'{len(context_str)=}')

    context_str = context_str[-1000:]
    print(f'截断后的{len(context_str)=}')


    generation = llm_chain.invoke({"question": question,"context":context_str})
    ai_message = AIMessage(content=generation)
    return {"messages": ai_message, "generation": generation}

def generate(state:RagSubgraphState):
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
    messages = state["messages"]
    if not isinstance(documents, list):
      documents = [documents]

    # RAG generation
    generation = rag_node.invoke({"documents": documents, "question": question, "messages":messages})
    print(generation)
    generation_message = ToolMessage(content=generation,name='generation',tool_call_id='0')
    return {"documents": documents, "question": question, "generation": generation, "messages":generation_message}

def grade_documents(state:RagSubgraphState):
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
            score = retrieval_document_relevance_grader.invoke({"question": question, "document": d.page_content})
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
    relevance_filtered_results = "\n".join([d.page_content for d in filtered_docs])
    relevance_filtered_message = ToolMessage(content=relevance_filtered_results,name='grade_documents',tool_call_id='0')
    return {"documents": filtered_docs, "question": question, "messages":relevance_filtered_message}

def web_search(state:RagSubgraphState):
    """
    Web search based on the re-phrased question.

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Updates documents key with appended web results
    """

    print("---WEB SEARCH---")
    question = state["question"]
    # Web search
    docs = get_web_search_documents(question)
    web_results = "\n".join([d.page_content for d in docs])

    # todo: 需对doc进行split和检索（embedding和/或rerank） 
    web_search_message = ToolMessage(content=web_results,name='web_search',tool_call_id='0')
    web_results_document = Document(page_content=web_results)
    return {"documents": web_results_document, "question_searched":{question:True},"messages":web_search_message}

def code_generation(state:RagSubgraphState):
    pass

def code_execution(state:RagSubgraphState):
    pass

def route_question(state:RagSubgraphState):
    """
    Route question to web search or RAG.

    Args:
        state (dict): The current graph state

    Returns:
        str: Next node to call
    """    
    print("---ROUTE QUESTION---")
    question = state["question"]

     # 更新消息列表
    source = question_router.invoke({"question": question})
    print(source)
    print(f"---ROUTE DESTINATION---")
    
    # Fallback to LLM
    if USING_OLLAMA_FUNCTIONS:
        try:
            tool_calls = source.additional_kwargs['function_call']
            # tool_calls = {'name': 'web_search', 'arguments': '{"query": "How to respond when someone asks \'how are you today?\'"}'}
        except:
            tool_calls = []
            print("---ROUTE QUESTION TO LLM---")
            return "llm_fallback" 
        if len(tool_calls) == 0:
            print("---Router Could Not Decide Where To GO (len[tool_calls]) == 0), SO ROUTE QUESTION TO LLM ---")
            return "llm_fallback"

        # Choose datasource
        datasource = tool_calls["name"]

    else:        
        try:
            tool_calls = source.tool_calls
        except:
            tool_calls = []
            print("---ROUTE QUESTION TO LLM---")
            return "llm_fallback" 
        if len(tool_calls) == 0:
            print("---Router Could Not Decide Where To GO (len[tool_calls]) == 0), SO ROUTE QUESTION TO LLM ---")
            return "llm_fallback"

        # Choose datasource
        datasource = tool_calls[0]["name"]


    if datasource == 'web_search':
        print("---ROUTE QUESTION TO WEB SEARCH---")
        return "web_search"
    elif datasource == 'vectorstore':
        print("---ROUTE QUESTION TO RAG---")
        return "vectorstore"
    elif datasource == 'code_generation':
        print("---ROUTE QUESTION TO CODE GENERATION---")
        return "code_generation"
    elif datasource == 'code_execution':
        print("---ROUTE QUESTION TO CODE EXECUTION---")
        return "code_execution"
    elif datasource in excutable_tool_names:
        print("---ROUTE QUESTION TO TOOL ASSISTANT---")


        # upadated_messages_source = add_messages(state["messages"],[source])
        # tool_excute_result = excutable_tool_node.invoke({"messages":upadated_messages_source})
        # upadated_messages_result = add_messages(upadated_messages_source,tool_excute_result['messages'])
        # state["messages"] = upadated_messages_result
        # print(tool_excute_result)

        return "tool_assistant"

    else: 
        print("---ROUTE QUESTION TO LLM---")
        return "llm_fallback"


def decide_to_generate(state:RagSubgraphState):
    """
    Determines whether to generate an answer, or re-generate a question.

    Args:
        state (dict): The current graph state

    Returns:
        str: Binary decision for next node to call
    """

    print("---DECIDED TO GENERATE OR WEB SEARCH BASED ON HAVINE ANY DOCUMENTS RELEVANT TO QUESTION ---")
    question = state["question"]
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

def grade_generation_v_documents_and_question(state:RagSubgraphState):
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

    print(f"{len(documents[0].page_content)=}")

    doc_num = len(documents)
    token_len = int(1000/doc_num)
    for i in range(doc_num):
        content = documents[i].page_content[-token_len:]
        documents[i].page_content = content
     
    # Check hallucination / answer_is_supported_by_documents    
    try:
        score = answer_is_supported_by_documents_grader.invoke({"documents": documents, "generation": generation})
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
            score = answer_grader.invoke({"question": question,"generation": generation})
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





## Build Graph

# Flow
rag_sub_graph = StateGraph(RagSubgraphState)
# Entry_Point 
rag_sub_graph.set_conditional_entry_point(
    route_question,
    {
        "llm_fallback": "llm_fallback",
        "web_search": "web_search",
        "vectorstore": "retrieve",
        "code_generation": "code_generation",
        "code_execution": "code_execution",        
    },
)

# Define the nodes
    # The first argument is the unique node name
    # The second argument is the function or object that will be called whenever the node is used.
rag_sub_graph.add_node("web_search", web_search) # web search
rag_sub_graph.add_node("retrieve", retrieve) # retrieve
rag_sub_graph.add_node("grade_documents", grade_documents) # grade documents
rag_sub_graph.add_node("generate", generate) 
rag_sub_graph.add_node("code_generation", code_generation) 
rag_sub_graph.add_node("code_execution", code_execution)
rag_sub_graph.add_node("llm_fallback", llm_fallback) # llm

# define the edges
rag_sub_graph.add_edge("web_search", "generate")
rag_sub_graph.add_edge("retrieve", "grade_documents")
rag_sub_graph.add_edge("code_generation", "code_execution")
rag_sub_graph.add_edge("code_execution", "llm_fallback")

rag_sub_graph.add_conditional_edges(
    "grade_documents",
    decide_to_generate,
    {
        "web_search": "web_search",
        "generate": "generate",
    },
)
rag_sub_graph.add_conditional_edges(
    "generate",
    grade_generation_v_documents_and_question,
    {
        # "not supported": "generate", # Hallucinations: re-generate 
        "not supported": END, # todo
        "not useful": "web_search", # Fails to answer question: fall-back to web-search 
        "useful": END,
    },
)
rag_sub_graph.add_edge("llm_fallback", END)

# Compile and Visualize
rag_compiled = rag_sub_graph.compile()
# The following functions interoperate between the top level graph state
# and the state of the research sub-graph
# this makes it so that the states of each graph don't get intermixed
rag_chain = functools.partial(sub_graph_enter_chain, members=members) | rag_compiled

rag_compiled.get_graph().print_ascii()  #Visualize this graph in ascii

# Run With Memory
def run_graph_workflow(question:str,config = {"recursion_limit":25,"configurable": {"thread_id": "UserName_SessionID"}}):
    memory = SqliteSaver.from_conn_string("checkpoints.sqlite")
    app = rag_sub_graph.compile(checkpointer=memory)   

    print('=*='*20)
    print(f"In Agent 'run_graph_workflow'：{question=}")
    inputs = {"question": question, "messages": [("human", question)]}
    try:
        events = app.stream(inputs, config, stream_mode="values")
        # print("=====events====="*5)
        # for event in events:
        #     print("-----event-----"*5)
        #     print(f"{event.keys()}")
        #     event["messages"][-1].pretty_print()
        #     # for m in event["messages"]:
        #     #     m.pretty_print()
        event = list(events)[-1]

        try:
            print("In Agent 'run_graph_workflow', answer:")
            result = event["generation"]
            print(result)
            
        except Exception as e:
            print(e) 
            raise e               
            
    except GraphRecursionError:
        print("!!!!!!GraphRecursionError: Graph recursion limit reached.!!!!!!")
        result = 'GraphRecursionError'
    except Exception as e:        
        print(f"!!!!!!Error: {e}.!!!!!!")
        result = f'出现了错误，你可以重新输入问题"{question}"再尝试几次。以下是错误的详细信息:{e}'
    return result
# aRun
async def arun_graph_workflow(question:str,config = {"recursion_limit":25,"configurable": {"thread_id": "-999"}}):
    async_memory = AsyncSqliteSaver.from_conn_string("checkpoints.async_sqlite")
    app = rag_sub_graph.compile(checkpointer=async_memory)

    print('=*='*20)
    print(f"In Agent 'arun_graph_workflow'：{question=}")
    inputs = {"question": question, "messages": [("human", question)]}
    try:
        value = await app.ainvoke(inputs, config)

        try:
            print("In Agent 'arun_graph_workflow', answer:")
            result = value["generation"]
            print(result)
        except Exception as e:
            print(e) 
            raise e               
            
    except GraphRecursionError:
        print("!!!!!!GraphRecursionError: Graph recursion limit reached.!!!!!!")
        result = 'GraphRecursionError'
    except Exception as e:
        
        print(f"!!!!!!Error: {e}.!!!!!!")
        result = f'出现了错误，你可以重新输入问题{question}再尝试几次。以下是错误的详细信息:{e}'
    return result

# aRun coro
def arun_coro_graph_workflow(question:str,config = {"recursion_limit":25,"configurable": {"thread_id": "-999"}}):
    async_memory = AsyncSqliteSaver.from_conn_string("checkpoints.async_sqlite")
    app = rag_sub_graph.compile(checkpointer=async_memory)

    print('=*='*20)
    print(f"In Agent 'arun_coro_graph_workflow'：{question=}")
    inputs = {"question": question, "messages": [("human", question)]}
    try:
        coro = app.ainvoke(inputs, config)
        value = asyncio.run(coro)

        try:
            print("In Agent 'arun_coro_graph_workflow', answer:")
            result = value["generation"]
            print(result)
        except Exception as e:
            print(e) 
            raise e               
            
    except GraphRecursionError:
        print("!!!!!!GraphRecursionError: Graph recursion limit reached.!!!!!!")
        result = 'GraphRecursionError'
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
        value=run_graph_workflow(question)

# """       
    print('\n\n')
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5) 
    print("~~~~test_memory~~~~"*5)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5)
    questions_test_memory = ["你知道我叫什么吗？","我叫张结魁，你叫什么呀？我们做好朋友吧","你还记得我叫什么吗?"] 
    for question in questions_test_memory:
        value=run_graph_workflow(question)
        # print(value)

    questions = ["What are the types of agent memory?","What player are the Bears expected to draft first in the 2024 NFL draft?","合肥是一个什么样的城市？","Hello, how are you today?"]
    print('\n\n')
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5) 
    print("$$$$run_graph_workflow$$$$"*5)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5) 
    for question in questions:
        value=run_graph_workflow(question)
        # print(value)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5)

    print('\n\n')
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5) 
    print("A&A&arun_graph_workflowA&A&"*5)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5) 
    for question in questions:
        # coro = arun_graph_workflow(question)
        value=asyncio.run(arun_graph_workflow(question))
        # print(value)
    print('END:A&A&arun_graph_workflowA&A&')

    print('\n\n')
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5) 
    print("B&B&arun_coro_graph_workflowB&B&"*5)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5) 
    for question in questions:
        result = arun_coro_graph_workflow(question)
        # print(result)
    print('END:B&B&arun_coro_graph_workflowB&B&')

# """



