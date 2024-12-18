from markitdown import MarkItDown

markitdown = MarkItDown()
# result = markitdown.convert("/data/projects/JqChatV2/UPLOAD_DOCS/knowledge_base/zjk_jqesclient_test/content/揭榜挂帅PPT汇报-基于DX的肺炎AI影像智能诊断.pptx")

result = markitdown.convert("/data/projects/JqChatV2/workspace/knowledge_base/testpdf/content/graphrag.pdf")
print(result.text_content)


