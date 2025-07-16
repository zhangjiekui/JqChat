
# curl http://10.1.150.105:9998/v1/chat/completions -H "Content-Type: application/json" -H 'Authorization: Bearer abc123' -d '{
#   "model": "qwen3",
#   "messages": [
#     {"role": "user", "content": "你好."}
#   ],
#   "temperature": 0.6,
#   "top_p": 0.95,
#   "top_k": 20,
#   "max_tokens": 32768
# }'


# {"id":"chatcmpl-e440450b31de44b7be9f8629c1826a65","object":"chat.completion","created":1752650799,"model":"qwen3","choices":[{"index":0,"message":{"role":"assistant","reasoning_content":"\n好的，用户发来“你好.”，我需要友好回应。首先，应该用中文回复，保持自然。用户可能只是打招呼，所以回应要简单热情。可以问他们需要什么帮助，或者用表情符号增加亲切感。注意不要用太正式的语言，保持轻松。同时检查是否有拼写错误，比如用户可能少打了句号，但“你好.”看起来没问题。确保回复简洁，不超过两句话。可能用户想开始对话，所以主动提供帮助比较好。最后，确认语气友好，符合之前的设定。\n","content":"\n\n你好！有什么我可以帮你的吗？😊","tool_calls":[]},"logprobs":null,"finish_reason":"stop","stop_reason":null}],"usage":{"prompt_tokens":10,"total_tokens":136,"completion_tokens":126,"prompt_tokens_details":null},"prompt_logprobs":null,"kv_transfer_params":null}


from typing import List
from fastmcp import FastMCP, Context
from jqcode.langgraph_in_class import GraphAgent
from fastmcp.server.dependencies import get_http_headers,get_context,get_http_request
from jqcode.jq_docstores.backend_docstore_utils.jq_es_metastores import JqElasticsearchUniMetaStore


default_kb_name = "zjk_jqesclient_reader_test_768im"
default_kb_description = "关于安徽晶奇网络科技股份有限公司（简称晶奇公司），以及医疗卫生、医疗健康、医疗服务、医疗政策、民政养老、社会救助、低保、低收入人口认定、退伍军人、优待抚恤等领域的政策文件、信息化产品、建设方案、技术文档等等方面的文档知识库。 凡是涉及安徽晶奇网络科技股份有限公司及以上领域相关的问题，或者是用户提及检索知识库或vectorstore时，都必须使用vectorstore工具。"


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
        if not kb_dict:
            print(f"知识库 {kb_name} 不存在，将返回默认的知识库信息！")
            kb_dict=  {"index_name": default_kb_name, "description":default_kb_description}
    return kb_dict

# @mcp.tool(
#     description="安徽晶奇公司智能体专家应用",
#     header_mapping={
#         "kb_name": "kb_name"  # 自动映射Header中的kb_name到参数
#     }
# )

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
    # mcp.run()
    mcp.run(transport="http", host="10.1.150.105", port=8500, path="/mcp")
    pass
# http://10.1.150.105:8500/mcp?kb=电子病历文书库
# http://10.1.150.105:8500/mcp?kb=zjk_jqesclient_reader_test_768im # 请检索知识库回答，医院信息系统中的基础维护系统完整功能详述
# http://10.1.150.105:8500/mcp?kb=社会救助知识库 # 请检索知识库回答，低收入人口的认定责任单位是？

