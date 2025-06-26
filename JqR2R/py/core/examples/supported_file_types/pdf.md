
# Graph RAG

EmergentAGI Inc. 08/08/24



# Many RAG algorithms

## Naive RAG

- **User Query**: 
  - **Documents**: 
    - **Indexing**: 
      - **Retrieval**: 
        - **Prompt**: Frozen LLM
        - **Output**: 

## Advanced RAG

- **User Query**: 
  - **Documents**: 
    - **Indexing**: 
      - **Retrieval**: 
        - **Post-retrieval**: 
          - **Rerank**: 
          - **Summary**: 
          - **Fusion**: 
        - **Prompt**: Frozen LLM
        - **Output**: 

## Modular RAG

- **Modules**: 
  - **Search**: 
    - **Routing**: 
      - **Retrieve**: 
        - **Rewrite**: 
        - **Demonstrate**: 
          - **Search**: 
          - **Predict**: 
            - **Read**: 
              - **Memory**: 
                - **Fusion**: 

- **Patterns**: 
  - **Native RAG**: 
    - **Retrieve**: 
      - **Retrieve**: 
        - **Rerank**: 
        - **Read**: 
          - **Memory**: 
            - **Fusion**: 
  - **Advanced RAG**: 
    - **Retrieve**: 
      - **Retrieve**: 
        - **Rerank**: 
        - **Read**: 
          - **Memory**: 
            - **Fusion**: 
  - **Iterative RAG**: 
    - **Retrieve**: 
      - **Retrieve**: 
        - **Rerank**: 
        - **Read**: 
          - **Memory**: 
            - **Fusion**: 
```

This markdown content captures the structure and flow of the RAG algorithms as depicted in the image, maintaining the original visual hierarchy and patterns.


# Global search

- Most existing algorithms struggle with population level queries such as
- Who are the main competitors of company X?
- List all people who have worked with person X
- What does Paul graham generally write about?

- These queries require information from a large amount of chunks to be answered correctly
- More efficient ways of information representation are needed



# GraphRAG

- Construct a graph on your dataset and query it using LLMs
- Natively supports population level queries, but construction is very expensive



# Triplex: SOTA LLM for Knowledge Graphs

## Entity Types
- PERSON, ORGANIZATION

## Relationships
- FOUNDED_BY

## Text
- Elon Musk is the founder of SpaceX

## Triplex
```json
{
  "entities_and_triples": [
    "[1], PERSON:Elon Musk",
    "[2], ORGANIZATION:SpaceX",
    "[2] FOUNDED_BY [1]"
  ]
}
```

## Benchmark
- Better than GPT-4o and 97% cheaper
- Blog: <https://www.sciphi.ai/blog/triplex>
- Demo: <https://kg.sciphi.ai>



# Triplex: SOTA LLM for Knowledge Graphs

## Entity Types
- PERSON, ORGANIZATION

## Relationships
- FOUNDED_BY

## Text
- Elon Musk is the founder of SpaceX

## Triplex
```json
{
  "entities_and_triples": [
    "[1], PERSON:Elon Musk",
    "[2], ORGANIZATION:SpaceX",
    "[2] FOUNDED_BY [1]"
  ]
}
```

## Benchmark
- Better than GPT-4o and 97% cheaper
- Blog: <https://www.sciphi.ai/blog/triplex>
- Demo: <https://kg.sciphi.ai>
