from langchain_community.graphs import Neo4jGraph
from jqcode.jq_docstores_neo4j.shared.constants import (PROJECT_ID, QUERY_TO_GET_CHUNKS, 
                                  QUERY_TO_DELETE_EXISTING_ENTITIES, 
                                  QUERY_TO_GET_LAST_PROCESSED_CHUNK_POSITION,
                                  QUERY_TO_GET_LAST_PROCESSED_CHUNK_WITHOUT_ENTITY,
                                  START_FROM_BEGINNING,
                                  START_FROM_LAST_PROCESSED_POSITION,
                                  DELETE_ENTITIES_AND_START_FROM_BEGINNING,
                                  QUERY_TO_GET_NODES_AND_RELATIONS_OF_A_DOCUMENT)
from jqcode.jq_docstores_neo4j.shared.schema_extraction import schema_extraction_from_text
from jqcode.jq_docstores_neo4j.create_chunks import CreateChunksofDocument
from jqcode.jq_docstores_neo4j.graphDB_dataAccess import graphDBdataAccess
from jqcode.jq_docstores_neo4j.document_sources.local_file import get_documents_from_file_by_path
from jqcode.jq_docstores_neo4j.entities.source_node import sourceNode
from jqcode.jq_docstores_neo4j.llm import get_graph_from_llm
from jqcode.jq_docstores_neo4j.document_sources.s3_bucket import *
from jqcode.jq_docstores_neo4j.document_sources.wikipedia import *
from jqcode.jq_docstores_neo4j.document_sources.youtube import *
from jqcode.jq_docstores_neo4j.shared.common_fn import *
from jqcode.jq_docstores_neo4j.make_relationships import *
from jqcode.jq_docstores_neo4j.document_sources.web_pages import *

import re
import sys
import shutil
import urllib.parse
import json
from datetime import datetime

from jqcode.jq_utils.logger import jqkj_logger,is_main_process,set_multiprocessing_context
logger = jqkj_logger(__file__).get_logger()


async def extract_graph_from_file_local_file(uri, userName, password, database, model, merged_file_path, fileName, allowedNodes, allowedRelationship, retry_condition):
  return await processing_source(uri, userName, password, database, model, fileName, [], allowedNodes, allowedRelationship, True, merged_file_path, retry_condition)
  
async def processing_source(uri, userName, password, database, model, file_name, pages, allowedNodes, allowedRelationship, is_uploaded_from_local=None, merged_file_path=None, retry_condition=None):
  """
   Extracts a Neo4jGraph from a file based on the model.
   
   Args:
   	 uri: URI of the graph to extract
     db_name : db_name is database name to connect graph db
   	 userName: Username to use for graph creation ( if None will use username from config file )
   	 password: Password to use for graph creation ( if None will use password from config file )
   	 file: File object containing the file to be used
   	 model: Type of model to use ('Diffbot'or'OpenAI GPT')
   
   Returns: 
   	 Json response to API with fileName, nodeCount, relationshipCount, processingTime, 
     status and model as attributes.
  """
  uri_latency = {}
  start_time = datetime.now()
  processing_source_start_time = time.time()
  start_create_connection = time.time()
  graph = create_graph_database_connection(uri, userName, password, database)
  end_create_connection = time.time()
  elapsed_create_connection = end_create_connection - start_create_connection
  logger.info(f'Time taken database connection: {elapsed_create_connection:.2f} seconds')
  uri_latency["create_connection"] = f'{elapsed_create_connection:.2f}'
  graphDb_data_Access = graphDBdataAccess(graph)

  start_get_chunkId_chunkDoc_list = time.time()
  total_chunks, chunkId_chunkDoc_list = get_chunkId_chunkDoc_list(graph, file_name, pages, retry_condition)
  end_get_chunkId_chunkDoc_list = time.time()
  elapsed_get_chunkId_chunkDoc_list = end_get_chunkId_chunkDoc_list - start_get_chunkId_chunkDoc_list
  logging.info(f'Time taken to create list chunkids with chunk document: {elapsed_get_chunkId_chunkDoc_list:.2f} seconds')
  uri_latency["create_list_chunk_and_document"] = f'{elapsed_get_chunkId_chunkDoc_list:.2f}'
  uri_latency["total_chunks"] = total_chunks

  start_status_document_node = time.time()
  result = graphDb_data_Access.get_current_status_document_node(file_name)
  end_status_document_node = time.time()
  elapsed_status_document_node = end_status_document_node - start_status_document_node
  logging.info(f'Time taken to get the current status of document node: {elapsed_status_document_node:.2f} seconds')
  uri_latency["get_status_document_node"] = f'{elapsed_status_document_node:.2f}'

  select_chunks_with_retry=0
  node_count = 0
  rel_count = 0
      
  if len(result) > 0:
    if result[0]['Status'] != 'Processing':      
      obj_source_node = sourceNode()
      status = "Processing"
      obj_source_node.file_name = file_name
      obj_source_node.status = status
      obj_source_node.total_chunks = total_chunks
      obj_source_node.model = model
      if retry_condition == START_FROM_LAST_PROCESSED_POSITION:
          node_count = result[0]['nodeCount']
          rel_count = result[0]['relationshipCount']
          select_chunks_with_retry = result[0]['processed_chunk']
      obj_source_node.processed_chunk = 0+select_chunks_with_retry
      logging.info(file_name)
      logging.info(obj_source_node)
      
      start_update_source_node = time.time()
      graphDb_data_Access.update_source_node(obj_source_node)
      end_update_source_node = time.time()
      elapsed_update_source_node = end_update_source_node - start_update_source_node
      logging.info(f'Time taken to update the document source node: {elapsed_update_source_node:.2f} seconds')
      uri_latency["update_source_node"] = f'{elapsed_update_source_node:.2f}'

      logging.info('Update the status as Processing')
      update_graph_chunk_processed = int(os.environ.get('UPDATE_GRAPH_CHUNKS_PROCESSED'))
      # selected_chunks = []
      is_cancelled_status = False
      job_status = "Completed"
      for i in range(0, len(chunkId_chunkDoc_list), update_graph_chunk_processed):
        select_chunks_upto = i+update_graph_chunk_processed
        logging.info(f'Selected Chunks upto: {select_chunks_upto}')
        if len(chunkId_chunkDoc_list) <= select_chunks_upto:
          select_chunks_upto = len(chunkId_chunkDoc_list)
        selected_chunks = chunkId_chunkDoc_list[i:select_chunks_upto]
        
        result = graphDb_data_Access.get_current_status_document_node(file_name)
        is_cancelled_status = result[0]['is_cancelled']
        logging.info(f"Value of is_cancelled : {result[0]['is_cancelled']}")
        if bool(is_cancelled_status) == True:
          job_status = "Cancelled"
          logging.info('Exit from running loop of processing file')
          break
        else:
          processing_chunks_start_time = time.time()
          node_count,rel_count,latency_processed_chunk = await processing_chunks(selected_chunks,graph,uri, userName, password, database,file_name,model,allowedNodes,allowedRelationship,node_count, rel_count)
          processing_chunks_end_time = time.time()
          processing_chunks_elapsed_end_time = processing_chunks_end_time - processing_chunks_start_time
          logging.info(f"Time taken {update_graph_chunk_processed} chunks processed upto {select_chunks_upto} completed in {processing_chunks_elapsed_end_time:.2f} seconds for file name {file_name}")
          uri_latency[f'processed_combine_chunk_{i}-{select_chunks_upto}'] = f'{processing_chunks_elapsed_end_time:.2f}'
          uri_latency[f'processed_chunk_detail_{i}-{select_chunks_upto}'] = latency_processed_chunk
          end_time = datetime.now()
          processed_time = end_time - start_time
          
          obj_source_node = sourceNode()
          obj_source_node.file_name = file_name
          obj_source_node.updated_at = end_time
          obj_source_node.processing_time = processed_time
          obj_source_node.processed_chunk = select_chunks_upto+select_chunks_with_retry
          if retry_condition == START_FROM_BEGINNING:
            result = graph.query(QUERY_TO_GET_NODES_AND_RELATIONS_OF_A_DOCUMENT, params={"filename":file_name})
            obj_source_node.node_count = result[0]['nodes']
            obj_source_node.relationship_count = result[0]['rels']
          else:  
            obj_source_node.node_count = node_count
            obj_source_node.relationship_count = rel_count
          graphDb_data_Access.update_source_node(obj_source_node)
      
      result = graphDb_data_Access.get_current_status_document_node(file_name)
      is_cancelled_status = result[0]['is_cancelled']
      if bool(is_cancelled_status) == True:
        logging.info(f'Is_cancelled True at the end extraction')
        job_status = 'Cancelled'
      logging.info(f'Job Status at the end : {job_status}')
      end_time = datetime.now()
      processed_time = end_time - start_time
      obj_source_node = sourceNode()
      obj_source_node.file_name = file_name
      obj_source_node.status = job_status
      obj_source_node.processing_time = processed_time

      graphDb_data_Access.update_source_node(obj_source_node)
      logging.info('Updated the nodeCount and relCount properties in Document node')
      logging.info(f'file:{file_name} extraction has been completed')


      # merged_file_path have value only when file uploaded from local
      
      if is_uploaded_from_local:
        gcs_file_cache = os.environ.get('GCS_FILE_CACHE')
        if gcs_file_cache == 'True':
          folder_name = create_gcs_bucket_folder_name_hashed(uri, file_name)
          delete_file_from_gcs(BUCKET_UPLOAD,folder_name,file_name)
        else:
          delete_uploaded_local_file(merged_file_path, file_name)  
      processing_source_func = time.time() - processing_source_start_time
      logging.info(f"Time taken to processing source function completed in {processing_source_func:.2f} seconds for file name {file_name}")  
      uri_latency["Processed_source"] = f'{processing_source_func:.2f}'
      if node_count == 0:
        uri_latency["Per_entity_latency"] = 'N/A'
      else:  
        uri_latency["Per_entity_latency"] = f'{int(processing_source_func)/node_count}/s'
      response = {}  
      response["fileName"] = file_name
      response["nodeCount"] = node_count
      response["relationshipCount"] = rel_count
      response["total_processing_time"] = round(processed_time.total_seconds(),2)
      response["status"] = job_status
      response["model"] = model
      response["success_count"] = 1
      
      return uri_latency, response
    else:
      logging.info('File does not process because it\'s already in Processing status')
  else:
    error_message = "Unable to get the status of document node."
    logging.error(error_message)
    raise Exception(error_message)

async def processing_chunks(chunkId_chunkDoc_list,graph,uri, userName, password, database,file_name,model,allowedNodes,allowedRelationship, node_count, rel_count):
  #create vector index and update chunk node with embedding
  if graph is not None:
    if graph._driver._closed:
      graph = create_graph_database_connection(uri, userName, password, database)
  else:
    graph = create_graph_database_connection(uri, userName, password, database)
  
  start_update_embedding = time.time()
  update_embedding_create_vector_index( graph, chunkId_chunkDoc_list, file_name)
  end_update_embedding = time.time()
  elapsed_update_embedding = end_update_embedding - start_update_embedding
  logging.info(f'Time taken to update embedding in chunk node: {elapsed_update_embedding:.2f} seconds')
  latency_processing_chunk = {"update_embedding" : f'{elapsed_update_embedding:.2f}'} 
  logging.info("Get graph document list from models")
  
  start_entity_extraction = time.time()
  graph_documents =  await get_graph_from_llm(model, chunkId_chunkDoc_list, allowedNodes, allowedRelationship)
  end_entity_extraction = time.time()
  elapsed_entity_extraction = end_entity_extraction - start_entity_extraction
  logging.info(f'Time taken to extract enitities from LLM Graph Builder: {elapsed_entity_extraction:.2f} seconds')
  latency_processing_chunk["entity_extraction"] = f'{elapsed_entity_extraction:.2f}'
  cleaned_graph_documents = handle_backticks_nodes_relationship_id_type(graph_documents)
  
  start_save_graphDocuments = time.time()
  save_graphDocuments_in_neo4j(graph, cleaned_graph_documents)
  end_save_graphDocuments = time.time()
  elapsed_save_graphDocuments = end_save_graphDocuments - start_save_graphDocuments
  logging.info(f'Time taken to save graph document in neo4j: {elapsed_save_graphDocuments:.2f} seconds')
  latency_processing_chunk["save_graphDocuments"] = f'{elapsed_save_graphDocuments:.2f}'

  chunks_and_graphDocuments_list = get_chunk_and_graphDocument(cleaned_graph_documents, chunkId_chunkDoc_list)

  start_relationship = time.time()
  merge_relationship_between_chunk_and_entites(graph, chunks_and_graphDocuments_list)
  end_relationship = time.time()
  elapsed_relationship = end_relationship - start_relationship
  logging.info(f'Time taken to create relationship between chunk and entities: {elapsed_relationship:.2f} seconds')
  latency_processing_chunk["relationship_between_chunk_entity"] = f'{elapsed_relationship:.2f}'
  
  distinct_nodes = set()
  relations = []
  for graph_document in graph_documents:
    #get distinct nodes
    for node in graph_document.nodes:
          node_id = node.id
          node_type= node.type
          if (node_id, node_type) not in distinct_nodes:
            distinct_nodes.add((node_id, node_type))
    #get all relations
    for relation in graph_document.relationships:
          relations.append(relation.type)

    node_count += len(distinct_nodes)
    rel_count += len(relations)
    print(f'node count internal func:{node_count}')
    print(f'relation count internal func:{rel_count}')
  return node_count,rel_count,latency_processing_chunk

def get_chunkId_chunkDoc_list(graph, file_name, documents:List[Document], retry_condition):
  if retry_condition is None:
    logger.info("Break down file into chunks")
    bad_chars = ['"', "\n", "'"]
    for i in range(0,len(documents)):
      text = documents[i].page_content
      for j in bad_chars:
        if j == '\n':
          text = text.replace(j, ' ')
        else:
          text = text.replace(j, '')
      documents[i]=Document(page_content=str(text), metadata=documents[i].metadata)
    create_chunks_obj = CreateChunksofDocument(documents, graph)
    chunks = create_chunks_obj.split_file_into_chunks()
    chunkId_chunkDoc_list = create_relation_between_chunks(graph,file_name,chunks)
    return len(chunks), chunkId_chunkDoc_list
  
  else:  
    chunkId_chunkDoc_list=[]
    chunks =  graph.query(QUERY_TO_GET_CHUNKS, params={"filename":file_name})
    
    if chunks[0]['text'] is None or chunks[0]['text']=="" :
      raise Exception(f"Chunks are not created for {file_name}. Please re-upload file and try.")    
    else:
      for chunk in chunks:
        chunk_doc = Document(page_content=chunk['text'], metadata={'id':chunk['id'], 'position':chunk['position']})
        chunkId_chunkDoc_list.append({'chunk_id': chunk['id'], 'chunk_doc': chunk_doc})
      
      if retry_condition ==  START_FROM_LAST_PROCESSED_POSITION:
        logging.info(f"Retry : start_from_last_processed_position")
        starting_chunk = graph.query(QUERY_TO_GET_LAST_PROCESSED_CHUNK_POSITION, params={"filename":file_name})
        if starting_chunk[0]["position"] < len(chunkId_chunkDoc_list):
          return len(chunks), chunkId_chunkDoc_list[starting_chunk[0]["position"] - 1:]
        
        elif starting_chunk[0]["position"] == len(chunkId_chunkDoc_list):
          starting_chunk = graph.query(QUERY_TO_GET_LAST_PROCESSED_CHUNK_WITHOUT_ENTITY, params={"filename":file_name})
          return len(chunks), chunkId_chunkDoc_list[starting_chunk[0]["position"] - 1:]
        
        else:
          raise Exception(f"All chunks of {file_name} are alreday processed. If you want to re-process, Please start from begnning")    
      
      else:
        logging.info(f"Retry : start_from_beginning with chunks {len(chunkId_chunkDoc_list)}")    
        return len(chunks), chunkId_chunkDoc_list
  
def get_source_list_from_graph(uri,userName,password,db_name=None):
  """
  Args:
    uri: URI of the graph to extract
    db_name: db_name is database name to connect to graph db
    userName: Username to use for graph creation ( if None will use username from config file )
    password: Password to use for graph creation ( if None will use password from config file )
    file: File object containing the PDF file to be used
    model: Type of model to use ('Diffbot'or'OpenAI GPT')
  Returns:
   Returns a list of sources that are in the database by querying the graph and
   sorting the list by the last updated date. 
 """
  logging.info("Get existing files list from graph")
  graph = Neo4jGraph(url=uri, database=db_name, username=userName, password=password)
  graph_DB_dataAccess = graphDBdataAccess(graph)
  if not graph._driver._closed:
      logging.info(f"closing connection for sources_list api")
      graph._driver.close()
  return graph_DB_dataAccess.get_source_list()

def update_graph(graph):
  """
  Update the graph node with SIMILAR relationship where embedding scrore match
  """
  graph_DB_dataAccess = graphDBdataAccess(graph)
  graph_DB_dataAccess.update_KNN_graph()

  
def connection_check_and_get_vector_dimensions(graph,database):
  """
  Args:
    uri: URI of the graph to extract
    userName: Username to use for graph creation ( if None will use username from config file )
    password: Password to use for graph creation ( if None will use password from config file )
    db_name: db_name is database name to connect to graph db
  Returns:
   Returns a status of connection from NEO4j is success or failure
 """
  graph_DB_dataAccess = graphDBdataAccess(graph)
  return graph_DB_dataAccess.connection_check_and_get_vector_dimensions(database)

def merge_chunks_local(file_name, total_chunks, chunk_dir, merged_dir):

  if not os.path.exists(merged_dir):
      os.mkdir(merged_dir)
  logging.info(f'Merged File Path: {merged_dir}')
  merged_file_path = os.path.join(merged_dir, file_name)
  with open(merged_file_path, "wb") as write_stream:
      for i in range(1,total_chunks+1):
          chunk_file_path = os.path.join(chunk_dir, f"{file_name}_part_{i}")
          logging.info(f'Chunk File Path While Merging Parts:{chunk_file_path}')
          with open(chunk_file_path, "rb") as chunk_file:
              shutil.copyfileobj(chunk_file, write_stream)
          os.unlink(chunk_file_path)  # Delete the individual chunk file after merging
  logging.info("Chunks merged successfully and return file size")
  
  file_size = os.path.getsize(merged_file_path)
  return file_size
  
def get_labels_and_relationtypes(graph):
  query = """
          RETURN collect { 
          CALL db.labels() yield label 
          WHERE NOT label  IN ['Chunk','_Bloom_Perspective_', '__Community__', '__Entity__'] 
          return label order by label limit 100 } as labels, 
          collect { 
          CALL db.relationshipTypes() yield relationshipType  as type 
          WHERE NOT type  IN ['PART_OF', 'NEXT_CHUNK', 'HAS_ENTITY', '_Bloom_Perspective_','FIRST_CHUNK'] 
          return type order by type LIMIT 100 } as relationshipTypes
          """
  graphDb_data_Access = graphDBdataAccess(graph)
  result = graphDb_data_Access.execute_query(query)
  if result is None:
     result=[]
  return result

def manually_cancelled_job(graph, filenames, source_types, merged_dir, uri):
  
  filename_list= list(map(str.strip, json.loads(filenames)))
  source_types_list= list(map(str.strip, json.loads(source_types)))
 
  for (file_name,source_type) in zip(filename_list, source_types_list):
      obj_source_node = sourceNode()
      obj_source_node.file_name = file_name
      obj_source_node.is_cancelled = True
      obj_source_node.status = 'Cancelled'
      obj_source_node.updated_at = datetime.now()
      graphDb_data_Access = graphDBdataAccess(graph)
      graphDb_data_Access.update_source_node(obj_source_node)
      obj_source_node = None
  return "Cancelled the processing job successfully"

def populate_graph_schema_from_text(text, model, is_schema_description_cheked):
  """_summary_

  Args:
      graph (Neo4Graph): Neo4jGraph connection object
      input_text (str): random text from PDF or user input.
      model (str): AI model to use extraction from text

  Returns:
      data (list): list of lebels and relationTypes
  """
  result = schema_extraction_from_text(text, model, is_schema_description_cheked)
  return {"labels": result.labels, "relationshipTypes": result.relationshipTypes}

def set_status_retry(graph, file_name, retry_condition):
    graphDb_data_Access = graphDBdataAccess(graph)
    obj_source_node = sourceNode()
    status = "Ready to Reprocess"
    obj_source_node.file_name = file_name
    obj_source_node.status = status
    obj_source_node.retry_condition = retry_condition
    obj_source_node.is_cancelled = False
    if retry_condition == DELETE_ENTITIES_AND_START_FROM_BEGINNING or retry_condition == START_FROM_BEGINNING:
        obj_source_node.processed_chunk=0
    if retry_condition == DELETE_ENTITIES_AND_START_FROM_BEGINNING:
        graph.query(QUERY_TO_DELETE_EXISTING_ENTITIES, params={"filename":file_name})
        obj_source_node.node_count=0
        obj_source_node.relationship_count=0
    logging.info(obj_source_node)
    graphDb_data_Access.update_source_node(obj_source_node)
