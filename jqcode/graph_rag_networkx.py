# 参考https://medium.com/data-science-in-your-pocket/hybrid-rag-graphrag-rag-combined-for-retrieval-using-llms-1011fb84cdbb
import os
import asyncio
from typing import Annotated, List, Dict, TypedDict, Optional, Sequence,Literal, Any,Union
from langchain_core.documents import Document
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_community.graphs.networkx_graph import NetworkxEntityGraph
from langchain.chains.llm import LLMChain
from langchain.chains import GraphQAChain
from pydantic import Field
from langchain_core.callbacks.manager import CallbackManagerForChainRun
from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import BasePromptTemplate


from langchain_community.chains.graph_qa.prompts import (
    ENTITY_EXTRACTION_PROMPT,
    GRAPH_QA_PROMPT,
)
from langchain_community.graphs.networkx_graph import NetworkxEntityGraph, get_entities
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_agent.tools.jq_retriever import get_retriever
from jqcode.jq_utils.logger import jqkj_logger,is_main_process
logger = jqkj_logger(__file__).get_logger()

class JqGraphRetriveChain:
    def __init__(self,llm,graph,entity_prompt=ENTITY_EXTRACTION_PROMPT,input_key= "query",context_key= "context", output_key= "result",verbose=True):
        self.entity_extraction_chain = LLMChain(llm=llm, prompt=entity_prompt)
        self.graph = graph
        self.input_key = input_key
        self.context_key = context_key
        self.output_key = output_key
        self.verbose = verbose

    def __call__(
        self,
        inputs: Dict[str, Any],
    ) -> Dict[str, str]:
        """Extract entities, look up info and answer question."""
        question = inputs[self.input_key]
        question_entity_string = self.entity_extraction_chain.run(question)
        question_entities = get_entities(question_entity_string)        
        context_documents = inputs.get(self.context_key,[]) 
        context = "\n\n".join([d.page_content for d in context_documents])
        if context:
            context_entity_string = self.entity_extraction_chain.run(context)
            context_entities = get_entities(context_entity_string) 
            question_entities = question_entities + context_entities        
        all_triplets = []
        question_entities = set(question_entities)
        for entity in question_entities:
            all_triplets.extend(self.graph.get_entity_knowledge(entity))
        result = "下面是从上文提取到的相关知识图谱三元组：" +"\n".join(all_triplets)
        document_for_all_triplets =Document(page_content=result)
        context_documents.append(document_for_all_triplets)
        return context_documents

class JqGraphRag():
    def __init__(self,documents:List[Document]=None,llm = env_models_instance.chat_model,index_name='zjk_jqesclient_test',verbose=True,visualize=True):
        gml_dir = env_models_instance.abs_workspace + '/graph' + '/' + index_name 
        gml_path = gml_dir + '/' + index_name + '.gml'
        if not os.path.exists(gml_dir):
            os.makedirs(gml_dir, exist_ok=True)
        
        if os.path.isfile(gml_path):
            graph = NetworkxEntityGraph.from_gml(gml_path)
        else:
            graph = NetworkxEntityGraph()    
        
        graph_transformer = LLMGraphTransformer(llm=llm)
        self.llm = llm
        self.gml_dir = gml_dir
        self.gml_path = gml_path
        self.graph_transformer = graph_transformer
        self.graph = graph
        self.documents = documents
        self.verbose = verbose
        self.visualize = visualize
        self.nodes_num = self.graph.get_number_of_nodes()
        logger.warning(f"初始化Graph时共有{self.nodes_num}个节点")
        if documents:
            self.graph_indexing()
        
    def graph_indexing(self,documents:List[Document]=None):
        documents = documents or self.documents
        if not documents:
            logger.warning(f"待建立图索引时，传入的documents为空，请在初始化graphrag对象时或是调用graph_indexing时，传入非空的documents列表")
            
        # graph_documents = self.graph_transformer.convert_to_graph_documents(documents)
        graph_documents = asyncio.run(self.graph_transformer.aconvert_to_graph_documents(documents))
        # Add nodes to the graph
        for node in graph_documents[0].nodes:
            self.graph.add_node(node.id)
        # Add edges to the graph
        for edge in graph_documents[0].relationships:
            self.graph._graph.add_edge(
                    edge.source.id,
                    edge.target.id,
                    relation=edge.type,
                )

            self.graph._graph.add_edge(
                    edge.target.id,
                    edge.source.id,
                    relation=edge.type+" by",
                )
        self.graph.write_to_gml(self.gml_path)
        self.nodes_num = self.graph.get_number_of_nodes()
        logger.warning(f"Graph_INDEXING完成后共有{self.nodes_num}个节点")
        if self.visualize:
            path=self.gml_path.replace(".gml",".svg")
            self.graph.draw_graphviz(path=path)
            
        return self.gml_path
        
    def get_graph_retriever_chain(self):
        graph_retriever_chain = JqGraphRetriveChain(llm=self.llm,graph=self.graph) 
        return graph_retriever_chain
    
    def graph_retrieving(self,question,documents):        
        graph_retriever_chain = self.get_graph_retriever_chain()
        docs = documents or self.documents
        context = "\n\n".join([d.page_content for d in docs])
        inputs = {"query":question,"context":context}
        graph_documents= graph_retriever_chain.invoke(inputs,config=env_models_instance.invoke_llm_config) 
         
    
    
if __name__ == '__main__':
    graph_rag = JqGraphRag()
