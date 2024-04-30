### Tracing (optional)
import os
import re
import langchain
import pprint
from typing import Literal
from langchain import hub
from langchain_core.output_parsers import StrOutputParser,JsonOutputParser
from langchain_core.messages import HumanMessage,SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.tools.tavily_search import TavilySearchResults ### Search
from jqcode.c0_init_env_models import get_langchain_chat_model
from jqcode.c0_init_env_models import get_emb_8k_rerank_model
from jqcode.c0_init_env_models import get_es_connection, get_es_searchstore_index_documents,get_es_searchstore_from_documents

from langchain_community.chat_models import ChatOllama
# Set UP: LLM, embeddings,web_search_tool
web_search_tool = TavilySearchResults()
llm = get_langchain_chat_model()
# llm = ChatOllama(name='Qwen110B',model='qwen:110b-chat-v1.5-q4_K_M', temperature=0)
embed_model,embedding_model_8k,reranker = get_emb_8k_rerank_model()

# Docs to index
### Build Index
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
    doc.page_content =  replace_multiple_newlines(doc.page_content)
    docs_list_cleaned.append(doc)

# Split
text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=512, chunk_overlap=0
)
doc_splits = text_splitter.split_documents(docs_list_cleaned)

# Add to vectorstore
es_connection = get_es_connection()
vectorstore = get_es_searchstore_index_documents(documents=doc_splits, es_connection=es_connection,embedding=embed_model,index_name='test')
retriever = vectorstore.as_retriever()

### Retrieval Grader

# Retrieval Grader Data model
class GradeDocuments(BaseModel):
    """Binary score for relevance check on retrieved documents."""
    binary: str = Field(description="Documents are relevant to the question, VALUE must be 'yes' or 'no'")

# Retrieval Grader Prompt
preamble = """You are a grader assessing relevance of a retrieved document to a user question. \nIf the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant.\nIt does not need to be a stringent test.The goal is to filter out erroneous retrievals.\nGive a binary classification 'yes' or 'no' to indicate whether the document is relevant to the question.\nProvide me the binary classification with JSON: a single KEY 'binary' and VALUE must be 'yes' or 'no'.No preamble or explaination.
"""
# structured_llm_documents_relevant_grader = llm.with_structured_output(GradeDocuments, method="json_mode")
structured_llm_documents_relevant_grader = llm.with_structured_output(GradeDocuments, include_raw=True)
grade_prompt = ChatPromptTemplate.from_messages(
    [
        ("system",preamble),
        ("human", "Retrieved document: \n\n {document} \n\n User question: {question}\n\nResponse me just a simple JSON: a single key 'binary', and the value must be 'yes' or 'no'"),
    ]
)
# Retrieval Grader
retrieval_grader = grade_prompt | structured_llm_documents_relevant_grader
# response =  retrieval_grader.invoke({"question": "张结魁", "document": "张结魁"})
# print("question: 张结魁, document: 张结魁",response)

question = "types of memory"
docs = retriever.invoke(question)
for doc in docs:
    print('==='*20)
    doc_txt = doc.page_content
    print(f"{question=}")
    print(f"doc_txt的类型：{type(doc_txt)}")
    # print(f"doc_txt的内容：{doc_txt}") #太长，根据需要取消注释
    response =  retrieval_grader.invoke({"question": question, "document": doc_txt})
    print(f"{response=}")


### RAG Generate
# Preamble
preamble = """You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, just say that you don't know. Use three sentences maximum and keep the answer concise."""

# Prompt
prompt = lambda x: ChatPromptTemplate.from_messages(
    [
        SystemMessage(preamble),
        HumanMessage(
            f"Question: {x['question']} \nAnswer: ",
            additional_kwargs={"documents": x["documents"]},
        )
    ]
)

# RAG Chain
rag_chain = prompt | llm | StrOutputParser()

# Run
question = "types of memory"
rag_chain_question = "types of memory"
docs = retriever.invoke(question)
rag_chain_generation = rag_chain.invoke({"documents": docs, "question": question}) #特别命名，留作后面验证用
generation = rag_chain_generation

### LLM Generate/Fallback
# Preamble
preamble = """You are an assistant for question-answering tasks. Answer the question based upon your knowledge. Use three sentences maximum and keep the answer concise."""


# Prompt
prompt = lambda x: ChatPromptTemplate.from_messages(
    [
        SystemMessage(preamble),
        HumanMessage(
            f"Question: {x['question']} \nAnswer: "
        )
    ]
)

# Chain
llm_chain = prompt | llm | StrOutputParser()

# Run
question = "Hi how are you?"
generation = llm_chain.invoke({"question": question})


### Supported Grader

# Supported Grader Data model
class GradeSupported(BaseModel):
    """Binary classification for whether an answer is supported by a set of facts."""
    binary: str = Field(description="Answer is supported by the facts, VALUE must be 'yes' or 'no'")

#Supported Grader Preamble
preamble = """You are a grader assessing whether an answer is supported by a set of facts.\nGive a binary classification 'yes' or 'no'  to indicate whether the answer is supported by a set of facts.\nProvide the binary classification as a JSON with a single KEY 'binary' and VALUE must be 'yes' or 'no', such as "binary":"yes" or "binary":"no", and no preamble or explaination. """

structured_llm_hallucinations_grader = llm.with_structured_output(GradeSupported, method="json_mode",include_raw=True)
# structured_llm_hallucinations_grader = llm.with_structured_output(GradeSupported, include_raw=True)
# Supported (Hallucination) Grader Prompt
hallucination_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", preamble),
        ("human", "Here are the set of facts: \n\n {documents} \n\n Here is the answer: {generation}"),
    ]
)

hallucination_grader = hallucination_prompt | structured_llm_hallucinations_grader 
# hallucination_hallucinations_grader_json_mode = hallucination_prompt | structured_llm_hallucinations_grader_json_mode
print(f'{generation=}')
# response =  hallucination_grader_default_function_mode.invoke({"documents": docs, "generation": generation})
response1 =  hallucination_grader.invoke({"documents": docs, "generation": generation})
print(response1['raw'].content)

# response =  hallucination_grader_default_function_mode.invoke({"documents": docs, "generation": rag_chain_generation})
response1 =  hallucination_grader.invoke({"documents": docs, "generation": rag_chain_generation})
print(f'{rag_chain_generation=}')
print(response1)

### Answer Grader

# Data model
class GradeAnswer(BaseModel):
    """Binary score to assess answer addresses question."""

    binary_score: str = Field(description="Answer addresses the question, 'yes' or 'no'")

# Preamble
preamble = """You are a grader assessing whether an answer addresses / resolves a question \n
Give a binary score 'yes' or 'no'. yes' means that the answer resolves the question. Must be: "binary_score":"yes" or "binary_score":"no" """

structured_llm_grader = llm.with_structured_output(GradeAnswer, include_raw=True)

# Prompt
answer_prompt = ChatPromptTemplate.from_messages(
    [
        ("system",preamble),
        ("human", "User question: \n\n {question} \n\n LLM generation: {generation}"),
    ]
)

answer_grader = answer_prompt | structured_llm_grader
print(f'{question=}')
print(f'{generation=}')
answer_grader.invoke({"question": question,"generation": generation})

rag_question='types of memory'
# rag_chain_generation
print(f'{rag_question=}')
print(f'{rag_chain_generation=}')
answer_grader.invoke({"question": rag_question,"generation": rag_chain_generation})

### GraphState
from typing_extensions import TypedDict
from typing import List

class GraphState(TypedDict):
    """|
    Represents the state of our graph.

    Attributes:
        question: question
        generation: LLM generation
        documents: list of documents
    """
    question : str
    generation : str
    documents : List[str]

## Graph Flow
from langchain.schema import Document

def retrieve(state):
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

def llm_fallback(state):
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

def generate(state):
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

def grade_documents(state):
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
        score = retrieval_grader.invoke({"question": question, "document": d.page_content})
        grade = score.binary_score
        if grade == "yes":
            print("---GRADE: DOCUMENT RELEVANT---")
            filtered_docs.append(d)
        else:
            print("---GRADE: DOCUMENT NOT RELEVANT---")
            continue
    return {"documents": filtered_docs, "question": question}

def web_search(state):
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
    web_results = Document(page_content=web_results)

    return {"documents": web_results, "question": question}

### Edges ###

def route_question(state):
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

    print(f"-------ROUTE DESTINATION:\n{source.name}")
    
    # Fallback to LLM or raise error if no decision
    if "tool_calls" not in source.additional_kwargs:
        print("---ROUTE QUESTION TO LLM---")
        return "llm_fallback" 
    if len(source.additional_kwargs["tool_calls"]) == 0:
      raise "Router could not decide source"

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
        return "vectorstore"

def decide_to_generate(state):
    """
    Determines whether to generate an answer, or re-generate a question.

    Args:
        state (dict): The current graph state

    Returns:
        str: Binary decision for next node to call
    """

    print("---ASSESS GRADED DOCUMENTS---")
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

def grade_generation_v_documents_and_question(state):
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

    score = hallucination_grader.invoke({"documents": documents, "generation": generation})
    grade = score.binary_score

    # Check hallucination
    if grade == "yes":
        print("---DECISION: GENERATION IS GROUNDED IN DOCUMENTS---")
        # Check question-answering
        print("---GRADE GENERATION vs QUESTION---")
        score = answer_grader.invoke({"question": question,"generation": generation})
        grade = score.binary_score
        if grade == "yes":
            print("---DECISION: GENERATION ADDRESSES QUESTION---")
            return "useful"
        else:
            print("---DECISION: GENERATION DOES NOT ADDRESS QUESTION---")
            return "not useful"
    else:
        pprint("---DECISION: GENERATION IS NOT GROUNDED IN DOCUMENTS, RE-TRY---")
        return "not supported"
    
## Build Graph
import pprint

from langgraph.graph import END, StateGraph

workflow = StateGraph(GraphState)

# Define the nodes
workflow.add_node("web_search", web_search) # web search
workflow.add_node("retrieve", retrieve) # retrieve
workflow.add_node("grade_documents", grade_documents) # grade documents
workflow.add_node("generate", generate) # rag
workflow.add_node("llm_fallback", llm_fallback) # llm

# Build graph
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
        "not supported": "generate", # Hallucinations: re-generate 
        "not useful": "web_search", # Fails to answer question: fall-back to web-search 
        "useful": END,
    },
)
workflow.add_edge("llm_fallback", END)

# Compile
app = workflow.compile()

# Run
inputs = {"question": "What player are the Bears expected to draft first in the 2024 NFL draft?"}
for output in app.stream(inputs):
    for key, value in output.items():
        # Node
        pprint.pprint(f"Node '{key}':")
        # Optional: print full state at each node
    pprint.pprint("\n---\n")

# Final generation
pprint.pprint(value["generation"])