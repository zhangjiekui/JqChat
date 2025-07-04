
# Graph RAG

## Many RAG algorithms

| User Query | Documents |
| --- | --- |
| Indexing | Retrieval |
| Prompt → Frozen LLM | Output |
| Naive RAG |

| User Query | Documents |
| --- | --- |
| Indexing | Retrieval |
| Prompt → Frozen LLM | Output |
| Advanced RAG |

| User Query | Documents |
| --- | --- |
| Indexing | Retrieval |
| Routing | Search |
| Retrieve | Predict |
| Demonstrate | Memory |
| Fusion | |
| Modular RAG |

## Global search

- Most existing algorithms struggle with population level queries such as
- Who are the main competitors of company X?
- List all people who have worked with person X
- What does Paul graham generally write about?

- These queries require information from a large amount of chunks to be answered correctly
- More efficient ways of information representation are needed

## GraphRAG

- Construct a graph on your dataset and query it using LLMs
- Natively supports population level queries, but construction is very expensive

## Triplex: SOTA LLM for Knowledge Graphs

| Entity Types | PERSON, ORGANIZATION |
| --- | --- |
| RELATIONSHIPS | FOUNDED BY |
| TEXT | Elon Musk is the founder of SpaceX |

| Entities_and_triples: |
| --- |
| "[1], PERSON:Elon Musk", |
| "[2], ORGANIZATION: SpaceX", |
| "[2] FOUNDED_BY [1]" |

| Benchmark |
| --- |
| gpt-3.5 (few-shot) |
| gpt-4o (zero-shot) |
| Triplex-tiny (zero-shot) |
| gpt-4o (few-shot) |
| Triplex (zero-shot) |

- Better than GPT-4o and 97% cheaper
- Blog: <https://www.sciphi.ai/blog/triplex>
- Demo: <https://kg.sciphi.ai>

======页面分割======

# Triplex: SOTA LLM for Knowledge Graphs

## Entity Types
- PERSON, ORGANIZATION

## Relationships
- FOUNDED_BY

## TEXT
- Elon Musk is the founder of SpaceX

## Benchmark
| gpt-3.5 (few-shot) | gpt-4o (zero-shot) | Triplex-tiny (zero-shot) | gpt-4o (few-shot) | Triplex (zero-shot) |
|---------------------|---------------------|--------------------------|--------------------|----------------------|
| 0.38               | 0.42               | 0.56                     | 0.58               | 0.59                 |

- Better than GPT-4o and 97% cheaper
- Blog: [https://www.sciphi.ai/blog/triplex](https://www.sciphi.ai/blog/triplex)
- Demo: [https://kg.sciphi.ai](https://kg.sciphi.ai)

## Example
Paul Graham Essays

- Q: How to create a successful startup according to Paul?

## Technical Skills and Innovation
The interconnectedness of Lisp hacking and startups suggests that skills in programming can directly influence entrepreneurial success. Engaging with Lisp hacking not only improves technical capabilities but also fosters innovative thinking essential for startups. This interconnectedness implies that individuals or organizations proficient in Lisp may have a competitive edge in the startup landscape, potentially leading to more successful ventures.

## Funding and Financial Backing
Wealthy individuals play a crucial role in the startup ecosystem by providing essential funding that enables startups to grow and develop. Their investments are often pivotal for turning seeds to scale their operations, innovate, and bring new products to market. This financial backing can significantly influence the success trajectory of these startups. Funding is identified as a crucial element for the establishment and growth of startups. It provides the necessary resources for operations and development, which are vital for any startup aiming to succeed in a competitive market.
