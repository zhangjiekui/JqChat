
# Graph RAG

## Many RAG algorithms

| User Query | Documents |
| --- | --- |
| Indexing | Retrieval |
| Prompt → Frozen LLM | Output |
| Naive RAG | Advanced RAG |

| Routing | Search | Predict |
| --- | --- | --- |
| Retrieve | RAG | Rerank |
| Read | Demonstrate | Memory |
| Fusion | | |

## Global search

- Most existing algorithms struggle with population level queries such as
- Who are the main competitors of company X?
- List all people who have worked with person X
- What does Paul graham generally write about?

These queries require information from a large amount of chunks to be answered correctly
More efficient ways of information representation are needed

## GraphRAG

- Construct a graph on your dataset and query it using LLMs
- Natively supports population level queries, but construction is very expensive

## Triplex: SOTA LLM for Knowledge Graphs

| Entity Types | PERSON, ORGANIZATION |
| --- | --- |
| RELATIONSHIPS | FOUNDED BY |
| TEXT | Elon Musk is the founder of SpaceX |

Better than GPT-4o and 97% cheaper
Blog: <https://www.sciphi.ai/blog/triplex>
Demo: <https://kg.sciphi.ai>



# Example
## Paul Graham Essays

- Q: How to create a successful startup according to Paul?

## Technical Skills and Innovation
The interconnectedness of Lisp hacking and startups suggests that skills in programming can directly influence entrepreneurial success. Engaging with Lisp hacking not only improves technical capabilities but also fosters innovative thinking essential for startups. This interconnectedness implies that individuals or organizations proficient in Lisp may have a competitive edge in the startup landscape, potentially leading to more successful ventures [Data: Relationships (f0fc2022-477a-4be6-b957-f6720133390d1)].

## Funding and Financial Backing
Wealthy individuals play a crucial role in the startup ecosystem by providing essential funding that enables startups to grow and develop. Their investments are often pivotal for turning seeds to scale their operations, innovate, and bring new products to market. This financial backing can significantly influence the success trajectory of these startups [Data: Relationships (02a3d3e8-4c6b-49e3-8754-68b726dc7e31)]. Funding is identified as a crucial element for the establishment and growth of startups. It provides the necessary resources for operations and development, which are vital for any startup aiming to succeed in a competitive market [Data: Reports (b2a3c8e8-4c6b-49e3-8754-68b726dc7e31)].
