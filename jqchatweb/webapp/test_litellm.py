import openai
client = openai.OpenAI(
    api_key="anything",
    base_url="http://0.0.0.0:4000"
)

# request sent to model set on litellm proxy, `litellm --model`
response = client.chat.completions.create(model="anything", messages = [
    {
        "role": "user",
        "content": "请给我写一个1000字的关于RAG的技术报告"
    }
])

print(response)


# docker run -d --network=host -v open-webui:/app/backend/data -e OLLAMA_BASE_URL=http://127.0.0.1:11434 --name jq-open-webui --restart always ghcr.nju.edu.cn/open-webui/open-webui:main
