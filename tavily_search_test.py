from tavily import TavilyClient

tavily_client = TavilyClient(api_key="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")
response = tavily_client.search("合肥今天的天气怎么样？")

print(response)