# pip install "openclaw-sdk[fastapi]"
# pypi: https://pypi.org/project/openclaw-sdk/
# github: https://github.com/masteryodaa/openclaw-sdk
# python版本要3.11以上

import socket
import asyncio
from openclaw_sdk import OpenClawClient
from openclaw_sdk.pipeline.pipeline import Pipeline


host: str = "10.1.150.105"
port: int = 6190
def openclaw_is_running(host: str = host, port: int = port) -> bool:
    """Return True if an OpenClaw gateway is reachable at the default local port."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False

async def main(query: str = "你是谁？", workspace = "employee",host: str = host, port: int = port):
    try:
    # ✅ 先 await 获取客户端实例
        _openclaw_is_running_or_not = openclaw_is_running()
        if not _openclaw_is_running_or_not:
            print(f"OpenClaw gateway is not running at the specified {host=} and {port=}.")
            raise ConnectionError(f"OpenClaw gateway is not running at the specified {host=} and {port=}.")
        else:
            gateway_ws_url=f"ws://{host}:{port}"
            client_oc = await OpenClawClient.connect(gateway_ws_url=gateway_ws_url)
            client_jq = await OpenClawClient.connect(openai_base_url="http://10.1.150.105:6190",api_key="3701ec102f394668505e82ac077c980ce67541964b34d4e0",max_retries=3)
            client = client_oc
            # 再使用 async with 管理生命周期
            async with client:
                print("\n--- Executing single-step query ---")
                agent = client.get_agent(workspace)
                result1 = await agent.execute(query)
                print(result1.content)

                print("\n--- Running a multi-step pipeline ---")

                result = await (
                    Pipeline(client)
                    .add_step("researcher", "research-bot", "Research: {topic}")
                    .add_step("writer", "writer-bot", "Write an article based on: {researcher}")
                    .run(topic="quantum computing")
                )
                print(result.final_result.content)
    except ConnectionError as e:
        print(f"连接失败: {e}")
    except Exception as e:
        print(f"执行出错: {e}")

if __name__ == "__main__":
    # q="你叫小龙虾，我是你的老板暴龙，是公司的研发总监，你需要协助我完成工作上的任务。首先请记住和更新相关信息"
    asyncio.run(main("我是谁？你是谁？"))