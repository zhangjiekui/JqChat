from typing import List
from fastmcp import FastMCP, Context
from jqcode.langgraph_in_class import GraphAgent
from fastmcp.server.dependencies import get_http_headers,get_http_request
from jqcode.jq_docstores.backend_docstore_utils.jq_es_metastores import JqElasticsearchUniMetaStore


default_kb_name = "zjk_jqesclient_reader_test_768im"
default_kb_description = "关于安徽晶奇网络科技股份有限公司（简称晶奇公司），以及医疗卫生、医疗健康、医疗服务、医疗政策、民政养老、社会救助、低保、低收入人口认定、退伍军人、优待抚恤等领域的政策文件、信息化产品、建设方案、技术文档等等方面的文档知识库。 \n凡是涉及安徽晶奇网络科技股份有限公司及以上领域相关的问题，或者是用户提及检索知识库或vectorstore时，都必须使用vectorstore工具。"


metastore = JqElasticsearchUniMetaStore()
mcp = FastMCP(name="JqAgent MCP Server")

def get_kbs() -> List[dict]:
    """提供全部知识库的名称和描述列表"""
    all_kbs_meta = metastore.get_all_docs()
    all_kbs = [kb["_source"] for kb in all_kbs_meta]
    all_kbs.sort(key=lambda x: x["index_name"])
    return all_kbs

def get_kb_dict(kb_name:str) -> dict:
    """根据知识库名称，提供全部知识库的名称和描述的字典dict"""
    if not kb_name:
        return {"index_name": default_kb_name, "description":default_kb_description}
    else:
        kb_dict = {}
        all_kbs = get_kbs()
        for _kb in all_kbs:
            if _kb["index_name"] == kb_name:
                kb_dict = _kb
                description = _kb.get("description",default_kb_description)
                if description!=default_kb_description:
                    description = f"{description}\n或者\n{default_kb_description}"
                kb_dict=  {"index_name": kb_name, "description":description}
                break
        if not kb_dict:
            print(f"知识库 {kb_name} 不存在，将返回默认的知识库信息！")
            kb_dict=  {"index_name": default_kb_name, "description":default_kb_description}
    return kb_dict

@mcp.tool()
def jqagent(query:str) -> str:
    f"""安徽晶奇公司网络科技公司研发的一款高级智能体专家应用，可以聊天对话，并具备以下工具和能力：
        get_flight_number - 查询航班号（需提供出发地/目的地/日期）
        python_repl_tool - 执行简单Python命令（适用于基础计算/逻辑处理）
        get_elderly_organization_list - 查找附近养老机构（需位置/半径/数量参数）
        WEB_SEARCH - 网络搜索（特别适用于2024年后时效性信息检索）
        CODE_GENERATION - 代码生成（专注数据处理/可视化/文件分析等复杂场景）
        CODE_EXECUTION - 代码执行（运行用户提供的代码片段并返回结果）
        VECTORSTORE - {default_kb_description}
    参数说明:
    :param query: 用户查询字符串
    """
    try:
        request=get_http_request()
        kb_name=request.query_params.get("kb","None")
        print(f"get from request: {kb_name=} ")
        if not kb_name:
            headers = get_http_headers(include_all=True)
            kb_name = headers.get("kb","None")
            print(f"get from headers: {kb_name=} ")

        kb_base_dict =  get_kb_dict(kb_name)   
        chat_bot = GraphAgent(kb_base_dict=kb_base_dict)
        text = chat_bot.run_conversation(user_question=query)
    except Exception as e:
        print(e)
        text = str(e)
    return text

if __name__ == "__main__":
    mcp.run(transport="http", host="10.1.150.105", port=8500, path="/mcp")

# http://10.1.150.105:8500/mcp?kb=电子病历文书库 #请查询病人高瑜的入院记录，并分析总结病情
# http://10.1.150.105:8500/mcp?kb=zjk_jqesclient_reader_test_768im # 请检索知识库回答，医院信息系统中的基础维护系统完整功能详述
# http://10.1.150.105:8500/mcp?kb=社会救助知识库 # 请检索知识库回答，低收入人口的认定责任单位是？


