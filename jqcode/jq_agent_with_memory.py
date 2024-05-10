# https://langchain-ai.github.io/langgraph/tutorials/introduction/
# https://github.com/langchain-ai/langgraph/blob/main/examples/persistence.ipynb
import re
import asyncio
import pprint
from langchain.schema import Document
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import GraphRecursionError
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage,SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.tools.tavily_search import TavilySearchResults ### Search
# from langchain_community.chat_models import ChatOllama
from jqcode.c0_init_env_models import get_langchain_chat_model
from jqcode.c0_init_env_models import get_emb_8k_rerank_model
from jqcode.c0_init_env_models import get_es_connection, get_es_searchstore, get_es_searchstore_index_documents


# Set UP: LLM, embeddings,web_search_tool
llm = get_langchain_chat_model() # llm = ChatOllama(name='Qwen110B',model='qwen:110b-chat-v1.5-q4_K_M', temperature=0)
embed_model,embedding_model_8k,reranker = get_emb_8k_rerank_model()
web_search_tool = TavilySearchResults(max_results=2,handle_tool_error=True)

### Build Index
index_name='test'
es_connection = get_es_connection()
if es_connection.indices.exists(index=index_name):
    print(f"已存在index='{index_name}'！跳过插入索引的环节。")
    vectorstore = get_es_searchstore(embedding=embed_model,es_connection=es_connection,index_name=index_name)

else:
# Docs to index
    urls = [
        "https://lilianweng.github.io/posts/2023-06-23-agent/",
        "https://lilianweng.github.io/posts/2023-03-15-prompt-engineering/",
        "https://lilianweng.github.io/posts/2023-10-25-adv-attack-llm/",
    ]

    # Load
    docs = [WebBaseLoader(url).load() for url in urls]
    docs_list = [item for sublist in docs for item in sublist]

    # Clean
    def replace_multiple_newlines(text):
        return re.sub(r'\n+', '\n', text)

    docs_list_cleaned = []
    for doc in docs_list:
        doc.page_content = replace_multiple_newlines(doc.page_content)
        docs_list_cleaned.append(doc)

    # Split
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=512, chunk_overlap=0
    )
    doc_splits = text_splitter.split_documents(docs_list_cleaned)

    # Add to vectorstore
    vectorstore = get_es_searchstore_index_documents(documents=doc_splits, es_connection=es_connection,embedding=embed_model,index_name=index_name)

retriever = vectorstore.as_retriever()

### Router
# Data model
class web_search(BaseModel):
    """
    The internet. Use web_search for questions that are related to anything else than agents, prompt engineering, and adversarial attacks.
    """
    query: str = Field(description="The query to use when searching the internet.")

class vectorstore(BaseModel):
    """
    A vectorstore containing documents related to agents, prompt engineering, and adversarial attacks. Use the vectorstore for questions on these topics.
    """
    query: str = Field(description="The query to use when searching the vectorstore.")

structured_llm_router = llm.bind_tools(tools=[web_search, vectorstore])

# Preamble
preamble_llm_router = """You are an expert at answer the user's question: (1)answer user directly if you do know how to response; or (2)routing a user question to a vectorstore or web search.
The vectorstore contains documents related to agents, prompt engineering, and adversarial attacks, use the vectorstore for questions on these topics.
Otherwise, use web-search if you don't know how to answer the questions."""
# Prompt
route_prompt = ChatPromptTemplate.from_messages(
    [
        ("system",preamble_llm_router),
        ("human", "{question}"),
    ]
)

question_router = route_prompt | structured_llm_router


### Coding Grader
# Coding Grader Data model
class GradeCodingRelavance(BaseModel):
    """Binary classification for a user question is relevant to code generating/code executing."""
    k: str = Field(description="Whether a user question is relevant to [code generating/executing,file processing/analyzing, data exploring/analyzing], k must be 'yes' or 'no'")
# Code Generating/Code Executing Relavance Grader Prompt
preamble_coding_relevant_grader = """You are a grader assessing relevance of a user question to [code generating/executing,file processing/analyzing, data exploring/analyzing]. Response me with a simple JSON string can be directly consumed by  ‘json.loads’ method, must be ‘{{"k":"yes"}}’ or  ‘{{"k":"no"}}’,'yes' means a user question is related to Python code generating/code executing.No preamble or explaination."""
# structured_llm_documents_relevant_grader = llm.with_structured_output(GradeDocumentsRelavance, method="json_mode", include_raw=True)
structured_llm_coding_relevant_grader = llm.with_structured_output(GradeCodingRelavance,method='json_mode')
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
# structured_llm_documents_relevant_grader = llm.with_structured_output(GradeDocumentsRelavance, method="json_mode", include_raw=True)
structured_llm_documents_relevant_grader = llm.with_structured_output(GradeDocumentsRelavance,method='json_mode')
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
rag_chain = prompt | llm | StrOutputParser()

### LLM Generate/Fallback
# Preamble
preamble_llm = """You are an assistant for question-answering tasks. Answer the question based upon your knowledge. Use three sentences maximum and keep the answer concise."""
# Prompt
prompt = lambda x: ChatPromptTemplate.from_messages(
    [
        SystemMessage(preamble_llm),
        HumanMessage(
            f"Question: {x['question']} \nAnswer: "
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
# structured_llm_hallucinations_grader = llm.with_structured_output(GradeSupported, method="json_mode",include_raw=True)
structured_llm_answer_is_supported_by_documents_grader = llm.with_structured_output(GradeSupported, method="json_mode")
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
structured_llm_answer_grader = llm.with_structured_output(GradeAnswer, method="json_mode")

# Prompt
answer_prompt = ChatPromptTemplate.from_messages(
    [
        ("system",preamble_answer_grader),
        ("human", "question: {question} \n\n answer: {generation}"),
    ]
)
# answer grader
answer_grader = answer_prompt | structured_llm_answer_grader

### GraphState
from typing import Annotated, List
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class State(TypedDict):
    """|
    Represents the state of our graph.

    Attributes:
        question: question
        generation: LLM generation
        documents: list of documents
        messages: Annotated[list, add_messages]
    """
    question : str
    generation : str
    documents : List[str]
    question_searched : dict
    messages: Annotated[list, add_messages]
        # Messages have the type "list". 
        # The `add_messages` function in the annotation defines how this state key should be updated
        # (in this case, it appends messages to the list, rather than overwriting them)

## Graph Flow


def retrieve(state:State):
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
    return {"documents": documents, "question": question}

def llm_fallback(state:State):
    """
    Generate answer using the LLM w/o vectorstore

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): New key added to state, generation, that contains LLM generation
    """
    print("---LLM Fallback---")
    question = state["question"]
    generation = llm_chain.invoke({"question": question})
    return {"question": question, "generation": generation}

def generate(state:State):
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
    if not isinstance(documents, list):
      documents = [documents]

    # RAG generation
    generation = rag_chain.invoke({"documents": documents, "question": question})

    return {"documents": documents, "question": question, "generation": generation}

def grade_documents(state:State):
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
        score = retrieval_document_relevance_grader.invoke({"question": question, "document": d.page_content})
        try:
            grade = score.k
            if grade == "yes":
                print("---GRADE: DOCUMENT RELEVANT---")
                filtered_docs.append(d)
            else:
                print("---GRADE: DOCUMENT NOT RELEVANT---")
                continue
        except Exception as e:
            print(f"---ERROR: 无法获取当前文档的'问题-文档相关性'的判别结果，详细错误信息如下:---")
            print(e)
            filtered_docs.append(d)

    return {"documents": filtered_docs, "question": question}

def web_search(state:State):
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
    docs = web_search_tool.invoke({"query": question})
    web_results = "\n".join([d["content"] for d in docs])
    print('Web Search Results:')
    print(web_results)

    web_results = Document(page_content=web_results)
    return {"documents": web_results, "question": question, "question_searched":{question:True}}

### Edges ###

def route_question(state:State):
    """
    Route question to web search or RAG.

    Args:
        state (dict): The current graph state

    Returns:
        str: Next node to call
    """

    print("---ROUTE QUESTION---")
    question = state["question"]
    source = question_router.invoke({"question": question})

    print(f"---ROUTE DESTINATION---")
    
    # Fallback to LLM or raise error if no decision
    if "tool_calls" not in source.additional_kwargs:
        print("---ROUTE QUESTION TO LLM---")
        return "llm_fallback" 
    if len(source.additional_kwargs["tool_calls"]) == 0:
        print("---Router Could Not Decide Where To GO (len[tool_calls]) == 0) ---")
        print("---SO ROUTE QUESTION TO LLM---")
        return "llm_fallback"

    # Choose datasource
    datasource = source.additional_kwargs["tool_calls"][0]["function"]["name"]
    if datasource == 'web_search':
        print("---ROUTE QUESTION TO WEB SEARCH---")
        return "web_search"
    elif datasource == 'vectorstore':
        print("---ROUTE QUESTION TO RAG---")
        return "vectorstore"
    else: 
        print("---ROUTE QUESTION TO LLM---")
        return "llm_fallback"

def decide_to_generate(state:State):
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

def grade_generation_v_documents_and_question(state:State):
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
 
    # Check hallucination / answer_is_supported_by_documents
    score = answer_is_supported_by_documents_grader.invoke({"documents": documents, "generation": generation})
    try:
        grade = score.k
    except Exception as e:
        grade = "yes" # 继续按正常往下执行！
        print(f"---ERROR: 无法获取'文档-答案支持性'的判别结果，详细错误信息如下:---")
        print(e)
        print("---正常往下执行---") 

    
    if grade == "yes":
        print("---DECISION: GENERATION IS GROUNDED IN DOCUMENTS---")
        # Check question-answering
        print("---GRADE GENERATION vs QUESTION---")
        score = answer_grader.invoke({"question": question,"generation": generation})
        
        try:
            grade = score.k
        except Exception as e:
            grade = "yes" # 继续按正常往下执行！
            print(f"---ERROR: 无法获取'答案-问题解决性'的判别结果，详细错误信息如下:---")
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

workflow = StateGraph(State)

# Define the nodes
    # The first argument is the unique node name
    # The second argument is the function or object that will be called whenever the node is used.

workflow.add_node("web_search", web_search) # web search
workflow.add_node("retrieve", retrieve) # retrieve
workflow.add_node("grade_documents", grade_documents) # grade documents
workflow.add_node("generate", generate) # rag
workflow.add_node("llm_fallback", llm_fallback) # llm

# define the edges
workflow.set_conditional_entry_point(
    route_question,
    {
        "web_search": "web_search",
        "vectorstore": "retrieve",
        "llm_fallback": "llm_fallback",
    },
)
workflow.add_edge("web_search", "generate")
workflow.add_edge("retrieve", "grade_documents")
workflow.add_conditional_edges(
    "grade_documents",
    decide_to_generate,
    {
        "web_search": "web_search",
        "generate": "generate",
    },
)
workflow.add_conditional_edges(
    "generate",
    grade_generation_v_documents_and_question,
    {
        # "not supported": "generate", # Hallucinations: re-generate 
        "not supported": END, # todo
        "not useful": "web_search", # Fails to answer question: fall-back to web-search 
        "useful": END,
    },
)
workflow.add_edge("llm_fallback", END)

# Compile
memory = AsyncSqliteSaver.from_conn_string("checkpoints.sqlite")
# app = workflow.compile()
app = workflow.compile(checkpointer=memory)

# app.get_graph().print_ascii()  #Visualize this graph in ascii

# Run
def run_graph_workflow(question:str,config = {"recursion_limit":25,"configurable": {"thread_id": "2"}}):
    print('=*='*20)
    print(f"In Agent 'run_graph_workflow'：{question=}")
    inputs = {"question": question}
    try:
        coro_app = app.ainvoke(inputs, config)
        value=asyncio.run(coro_app) 
        try:
            print("In Agent 'run_graph_workflow', answer:")
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
        result = f'出现了错误，你可以重新输入问题"{question}"再尝试几次。以下是错误的详细信息:{e}'
    return result
# aRun
async def arun_graph_workflow(question:str,config = {"recursion_limit":25,"configurable": {"thread_id": "2"}}):
    print('=*='*20)
    print(f"In Agent 'arun_graph_workflow'：{question=}")
    inputs = {"question": question}
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



if __name__ == '__main__':

    questions = ["What are the types of agent memory?","What player are the Bears expected to draft first in the 2024 NFL draft?","合肥是一个什么样的城市？","Hello, how are you today?"]
    print("$$$$run_graph_workflow$$$$"*5)
    for question in questions:
        value=run_graph_workflow(question)
        # print(value)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5) 
    print("A&A&arun_graph_workflowA&A&"*5)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~"*5) 
    for question in questions:
        coro = arun_graph_workflow(question)
        value=asyncio.run(coro)
        # print(value)
    print('END PROGRAM')






