import json_repair

a = json_repair.loads('{"name": "WEB_SEARCH, "arguments": "{"query": "What is the weather in SF and LA?"}""}')
print(a)