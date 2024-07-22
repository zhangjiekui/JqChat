from langchain_ollama import ChatOllama

llm = ChatOllama(model="llama3-groq-tool-use")
llm.invoke("Sing a ballad of LangChain.")