from langchain_community.cache import SQLAlchemyCache
from sqlalchemy import Column, Computed, Index, Integer, Sequence, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_utils import TSVectorType

Base = declarative_base()

"""
一、运行docker:配置中文时区和编码
        docker run -d --name postgres_cn \
        -v ~/pgdata:/var/lib/postgresql/data \
        --cap-add=SYS_PTRACE --privileged=true \
        --env POLARDB_PORT=5432 \
        --env POLARDB_USER=langchain \
        --env POLARDB_PASSWORD=langchain \
        --env POLARDB_DB=postgres \
        --env POSTGRES_INITDB_ARGS="--locale=zh_CN.utf8 --lc-collate=zh_CN.utf8 --lc-ctype=zh_CN.utf8 --encoding=UTF8" \
        --restart=always \
        -p 7000:5432 \
        polardb15_vector_age_zh:v1.2

二、（可选）安装Zhparser中文分词并修改配置文件
    使用vscode连接附加该容器，命令行执行下面
    ### Zhparser
        #### 1.安装SCWS
        ```
        cd ~
        wget -q -O - http://www.xunsearch.com/scws/down/scws-1.2.3.tar.bz2 | tar xjf -
        cd scws-1.2.3 ; ./configure ; sudo make install
        ```

        #### 2.安装Zhparser
        ```
        cd ~
        git clone https://github.com/amutu/zhparser.git
        cd zhparser
        make && make install
        ```
    ### vscode打开并修改配置文件\var\polardb\primary_datadir\postgresql.conf
        找到下面的内容部分
        -------
        lc_messages = 'en_US.UTF-8'			# locale for system error message
                            # strings
        lc_monetary = 'en_US.UTF-8'			# locale for monetary formatting
        lc_numeric = 'en_US.UTF-8'			# locale for number formatting
        lc_time = 'en_US.UTF-8'				# locale for time formatting

        # default configuration for text search
        default_text_search_config = 'pg_catalog.english'
        -------

        替换为：
        ------------------
        lc_messages = 'zh_CN.utf8'			# locale for system error message
                            # strings
        lc_monetary = 'zh_CN.utf8'			# locale for monetary formatting
        lc_numeric = 'zh_CN.utf8'			# locale for number formatting
        lc_time = 'zh_CN.utf8'				# locale for time formatting

        # default configuration for text search
        default_text_search_config='zhparser' 
        shared_preload_libraries = 'zhparser.so'
        shared_preload_libraries ='zhparser.so,\$libdir/polar_vfs,\$libdir/polar_io_stat,\$libdir/polar_monitor_preload,\$libdir/polar_worker'

        修改生效：vscode中找到该容器（postgres_cn），右键restart该容器
        ------------------
# https://help.aliyun.com/zh/analyticdb/analyticdb-for-postgresql/user-guide/use-zhparser-to-perform-chinese-word-segmentation
三、创建扩展并配置
    pgAdmin psql 连接该服务器
        ```psql 拷贝下面的命令，黏贴执行
            CREATE EXTENSION age;
            CREATE EXTENSION vector;
            CREATE EXTENSION zhparser;
            CREATE TEXT SEARCH CONFIGURATION zhparser (PARSER = zhparser);
            # SET zhparser.multi_zall = on;
            SET zhparser.multi_zall = off;
            ALTER TEXT SEARCH CONFIGURATION zhparser ADD MAPPING FOR n,v,a,i,e,l,x WITH simple;
        ``` 
        --上行的解释：添加名词（n）、动词（v）、形容词（a）、成语（i）、叹词（e）、习用语（l）、未知词（x）七种分词策略

        -------下面是更改映射的命令示例
            # ALTER TEXT SEARCH CONFIGURATION zhparser DROP MAPPING FOR e;  -- 移除某个映射的命令
            # ALTER TEXT SEARCH CONFIGURATION zhparser ADD MAPPING FOR e WITH simple;  -- 增加某个映射的命令
            # ALTER TEXT SEARCH CONFIGURATION zhparser ALTER MAPPING FOR x WITH english_stem, simple; -- 更改某个映射的命令
            -- 查询所有已注册解析器
            SELECT * FROM pg_ts_parser;
            -- 查看 zhparser 解析器支持的 token 类型
            SELECT * FROM ts_token_type('zhparser');
            SELECT * FROM ts_token_type('default');

------------------

四、测试配置
    ```psql
    show default_text_search_config;
    show shared_preload_libraries;

    SELECT to_tsvector('zhparser', '保障房资金压力');
    SELECT websearch_to_tsquery('zhparser', '华为云 OR 数据库');
    SELECT to_tsvector('zhparser', 'Test In English');
    SELECT to_tsvector('zhparser', '测试中文和English混合文本,Test In English');  =>  'english':3,8 'in':7 'test':6 '中文':2 '文本':5 '测试':1 '混合':4
    SELECT to_tsvector('english', '测试中文和English混合文本,Test In English');   =>  'english':4 'test':2 '测试中文和english混合文本':1

    SELECT to_tsquery('zhparser', '保障房资金压力');
    SELECT to_tsquery('zhparser', 'CREATE EXTENSION vector'); #会报错，该方法不支持英语场景
    SELECT to_tsquery('english', 'CREATE EXTENSION vector'); #会报错
    # 使用plainto_tsquery或phraseto_tsquery可以支持中英文
    SELECT plainto_tsquery('zhparser', 'CREATE EXTENSION vector');#正确运行   => 'create' & 'extension' & 'vector'
    SELECT plainto_tsquery('english', 'CREATE EXTENSION vector');#正确运行    => 'creat' & 'extens' & 'vector'
    SELECT phraseto_tsquery('zhparser', 'CREATE EXTENSION vector');#正确运行  => 'create' & 'extension' & 'vector'
    SELECT phraseto_tsquery('english', 'CREATE EXTENSION vector');#正确运行   => 'creat' & 'extens' & 'vector'
    SELECT to_tsquery('zhparser', 'Test In English');#会报错
    SELECT phraseto_tsquery('zhparser', 'Test In English');#正确运行
    SELECT phraseto_tsquery('zhparser', '测试中文和English混合文本,Test In English');#正确运行
"""

# https://python.langchain.com/docs/integrations/llm_caching/
class ZhFulltextLLMCache(Base):  # type: ignore
    """Postgres table for fulltext-indexed LLM Cache"""

    __tablename__ = "llm_cache_fulltext"
    id = Column(Integer, Sequence("cache_id"), primary_key=True)
    prompt = Column(String, nullable=False)
    llm = Column(String, nullable=False)
    idx = Column(Integer)
    response = Column(String)
    prompt_tsv = Column(
        TSVectorType(),
        Computed("to_tsvector('zhparser', llm || ' ' || prompt)", persisted=True),
    )
    __table_args__ = (
        Index("idx_fulltext_prompt_tsv", prompt_tsv, postgresql_using="gin"),
    )

