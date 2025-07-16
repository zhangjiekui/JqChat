"""
1. 创建客户端
2. 获取工具和资源和prompt
3. 执行工具

"""
import asyncio
from fastmcp import Client

async def run():
    client=Client("http://10.1.150.105:8500/mcp?kb=社会救助知识库")
    async with client:                      # 必要，用来进入上下文管理器
        tools = await client.list_tools()

        tool = tools[0]
        tool_result = await client.call_tool(tool.name,{"query":"请检索知识库回答，低收入人口的认定责任单位是？"})
        print(tools)
        print(tool_result)

if __name__=='__main__':
    asyncio.run(run())