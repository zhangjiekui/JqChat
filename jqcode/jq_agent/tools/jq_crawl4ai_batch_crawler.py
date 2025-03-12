from crawl4ai import RateLimiter,MemoryAdaptiveDispatcher,SemaphoreDispatcher,CrawlerMonitor, DisplayMode,AsyncWebCrawler
from crawl4ai import BrowserConfig,CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import BM25ContentFilter

from langchain_core.documents import Document
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

async def crawl4ai_get_search_result_documents(urls:list,question:str,query:str,max_doc_nums:int=4):
    browser_config = BrowserConfig(headless=True, verbose=False)
    bm25_filter = BM25ContentFilter(user_query=query,bm25_threshold=1.2)

    md_generator_config = DefaultMarkdownGenerator(
        content_filter=bm25_filter,
        options={
            "ignore_links": True,
            "ignore_images": True,
            "skip_internal_links ": True,
            "include_sup_sub": True,
            "escape_html": False,
            "body_width": 0
        }
    )

    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=md_generator_config,
        stream=False  # Default: get all results at once
    )

    dispatcher = SemaphoreDispatcher(
        max_session_permit=20,         # Maximum concurrent tasks
        rate_limiter=RateLimiter(      # Optional rate limiting
            base_delay=(0.5, 1.0),
            max_delay=10.0
        ),
        monitor=CrawlerMonitor(        # Optional monitoring
            max_visible_rows=15,
            display_mode=DisplayMode.DETAILED
    )
)
    async with AsyncWebCrawler(config=browser_config) as crawler:
        
        # Get all results at once
        results = await crawler.arun_many(
            urls=urls,
            config=run_config,
            dispatcher=dispatcher
        )

        docs_transformed_completed = []
        # Process all results after completion
        for result in results:
            if result.success:
                # await process_result(result)
                page_content = result.markdown.strip()
                length = len(page_content)
                if 20000>length>500:
                    source =  result.redirected_url
                    title = result.metadata.get('title','')
                    description = result.metadata.get('description','')
                    metadata = {"source":source,"title":title,"description":description}
                    transformed_document = Document(page_content=page_content, metadata=metadata) 

                    docs_transformed_completed.append(transformed_document)

                    # try:
                    #     from jqcode.langgraph_in_class import retrieval_document_relevance_grader
                    #     if question!=query:
                    #         q_str = f"用户问题：'{question}'及'搜索语句: {query}'"
                    #     else:
                    #         q_str = question
                    #     # grade = retrieval_document_relevance_grader.invoke({"document":page_content,"question":q_str})
                    #     grade = await retrieval_document_relevance_grader.ainvoke({"document":page_content,"question":q_str})
                    #     relavant = grade.k
                    #     if relavant == "yes": 
                    #         docs_transformed_completed.append(transformed_document)

                    # except Exception as e:
                    #     logger.warning(f"无法获取网页内容与问题的相关性评分：{e}，但仍然加入")
                    #     docs_transformed_completed.append(transformed_document)
            if not result.success:
                print(f"Failed to crawl {result.url}: {result.error_message}")


            if len(docs_transformed_completed) == max_doc_nums:
                break

        return docs_transformed_completed