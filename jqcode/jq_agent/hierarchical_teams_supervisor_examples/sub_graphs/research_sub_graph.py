from typing import Annotated, List, TypedDict

from langchain_community.document_loaders import WebBaseLoader
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import tool
import functools
from langsmith import trace
from langgraph.graph import END, StateGraph
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph.message import add_messages

from jqcode.jq_agent.c0_init_env_models import get_langchain_chat_model
from jqcode.jq_agent.hierarchical_teams_supervisor_examples.graph_create_utils import create_team_supervisor, create_agent, agent_node, sub_graph_enter_chain, get_graph_nodes
from jqcode.jq_agent.hierarchical_teams_supervisor_examples.graph_create_utils import supervisor_post_process_node,get_last_state, get_custom_supervisor_node,llm

from langchain_core.runnables import Runnable,RunnablePassthrough,RunnableLambda

from tools.jq_web_search_engine import get_web_search_documents



# Research team tools
tavily_tool = TavilySearchResults(max_results=2)
# @tool
# def scrape_webpages(urls: List[str]) -> str:
#     """Use requests and bs4 to scrape the provided web pages for detailed information."""
#     loader = WebBaseLoader(urls, continue_on_failure=True)
#     docs = loader.aload()
#     docs_content = "\n\n".join(
#         [
#             f'\n{doc.page_content}\n'
#             for doc in docs
#         ]
#     )
#     return docs_content

@tool
def search_and_scrape(query:str) -> str :
    """会智能选择使用Baidu、Bing检索query,然后爬取urls结果，或直接利用TavilySearch获取query的网络查询结果，返回清洗过的文本"""
    docs = get_web_search_documents(query,max_doc_nums=2)
    docs_content = "\n\n".join(
        [
            f'\n{doc.page_content}\n'
            for doc in docs
        ]
    )
    print(f'search_and_scrape返回的文本长度为：{len(docs_content)}')
    return docs_content

# Research team graph state
class ResearchTeamState(TypedDict):
    # A message is added after each team member finishes
    messages: Annotated[List[BaseMessage], add_messages]
    # The team members are tracked so they are aware of
    # the others' skill-sets
    team_members: List[str]
    # Used to route work. The supervisor calls a function
    # that will update this every time it makes a decision
    next: str
    question:str

search_agent = create_agent(
    llm,
    [tavily_tool],
    "You are a research assistant who can search for up-to-date info using the tavily search engine. Preferred",
)
search_node = functools.partial(agent_node, agent=search_agent, name="Search")

research_agent = create_agent(
    llm,
    [search_and_scrape],
    "You are a research assistant who can 智能选择使用Baidu、Bing检索query,然后爬取urls结果，或直接利用TavilySearch获取query的网络查询结果，返回清洗过的文本.仅作为备选工具，因为速度很慢，文本长度也不可控",
)
research_node = functools.partial(agent_node, agent=research_agent, name="Web Scraper")

members = ["Search", "Web Scraper"]
supervisor_agent = create_team_supervisor(
    llm,
    " You are a supervisor tasked with managing a conversation between the"
    " following workers:  Search, Web Scraper, the workers can search and get web content.  Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status. When finished,"
    " respond with FINISH.",
    members,
)

research_graph = StateGraph(ResearchTeamState)
research_graph.add_node("Search", search_node)
research_graph.add_node("Web Scraper", research_node)
# research_graph.add_node("supervisor", supervisor_agent) todo

custom_supervisor_node = get_custom_supervisor_node(supervisor_agent, members, graph_name = 'research_graph')
research_graph.add_node("supervisor", custom_supervisor_node)

# Define the control flow
research_graph.add_edge("Search", "supervisor")
research_graph.add_edge("Web Scraper", "supervisor")
research_graph.add_conditional_edges(
    "supervisor",
    lambda x: x["next"],
    {"Search": "Search", "Web Scraper": "Web Scraper", "FINISH": END }
)


research_graph.set_entry_point("supervisor")
research_graph_compiled = research_graph.compile()


# The following functions interoperate between the top level graph state
# and the state of the research sub-graph
# this makes it so that the states of each graph don't get intermixed
# members = get_graph_nodes(research_graph)
# print(members)
# ['Search', 'Web Scraper']
research_chain = functools.partial(sub_graph_enter_chain, members=members) | research_graph_compiled