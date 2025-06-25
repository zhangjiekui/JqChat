Graph RAG

EmergentAGI Inc. 08/08/24

# Many RAG algorithms

## Naive RAG

- **User Query**
- **Documents**
- **Indexing**
- **Retrieval**
- **Prompt** >>> **Frozen LLM**
- **Output**

## Advanced RAG

- **User Query**
- **Documents**
- **Indexing**
- **Retrieval**
- **Rewrite**
- **Retrieve**
- **Rerank**
- **Read**
- **Predict**
- **Read**
- **Fusion**
- **Prompt** >>> **Frozen LLM**
- **Output**

## Modular RAG

### Modules

- **Routing**
- **Search**
- **Retrieve**
- **Rewrite**
- **RAG**
- **Rerank**
- **Read**
- **Memory**
- **Fusion**

### Patterns

- **Rewrite**
- **Retrieve**
- **Rerank**
- **Search**
- **Retrieve**
- **Read**
- **Read**
- **Predict**
- **Read**

### Methods

| Method | Retrieval Source | Retrieval Data Type | Retrieval Granularity | Augmentation Stage | Retrieval Process |
|--------|------------------|--------------------|-----------------------|-------------------|------------------|
| CGL12 | Wikipedia        | Text               | Phrase                | Pre-training      | Iterative         |
| DenaX10 | FactoidWiki     | Text               | Posponizer           | Tuning             | Tuning            |
| EAR31 | Dataset-base     | Text               | Sentence              | Tuning             | Tuning            |
| UPISE20 | Dataset-base    | Text               | Sentence              | Tuning             | Tuning            |
| RAST32 | Dataset-base    | Text               | Sentence              | Tuning             | Tuning            |
| SaIF94m | Dataset-base    | Text               | Sentence              | Tuning             | Tuning            |
| FLARE11 | Search Engine Wiki | Text               | Sentence              | Tuning             | Tuning            |
| PGR42 | Wikipedia        | Text               | Sentence              | Tuning             | Tuning            |
| FLL11 | Wikipedia        | Text               | Sentence              | Tuning             | Tuning            |
| RAD15 | Dataset-base    | Text               | Sentence              | Tuning             | Tuning            |
| Filter errata16 | Synthesized dataset | Text | Sentence Pair | Tuning | Tuning |
| R-QA17 | Dataset-base    | Text               | Sentence Pair | Tuning | Tuning |
| LLM-R38 | Dataset-base    | Text               | Sentence Pair | Tuning | Tuning |
| TIGER40 | Dataset-base    | Text               | Item-base           | Pre-training | Tuning |
| LM-baker41 | Dataset-base    | Text               | Item-base           | Tuning | Tuning |
| BEEQE31 | Dataset-base    | Text               | Item-base           | Tuning | Tuning |
| CV-AQ1 | Synthesized dataset | Text | Item-base | Tuning | Tuning |
| Ada12 | Wikipedia        | Text               | Chunk               | Pre-training | Iterative |
| RA-VAEN | Wikipedia        | Text               | Chunk               | Pre-training | Iterative |
| RETM04 | Pre-training Corpus | Text | Chunk | Pre-training | Iterative |
| INSTRUCTION15 | Pre-training corpus | Text | Chunk | Tuning | Tuning |
| KRR1 | Search Engine Dataset | Text | Chunk | Tuning | Tuning |
| RA-c2s | Dataset-base    | Text               | Chunk               | Tuning | Tuning |
| PROMPTMAGATOR21 | BERT | Text | Chunk | Tuning | Tuning |
| AaD12 | MBERT+GPT+Wikipedia | Text | Chunk | Tuning | Tuning |
| RA-LAT2 | Common Corpus Wikipedia | Text | Chunk | Tuning | Tuning |
| RAG-Robots18 | Wikipedia | Text | Chunk | Tuning | Tuning |
| RA-Lang-Fors19 | Wikipedia | Text | Chunk | Tuning | Tuning |
| CnN52 | Wikipedia | Text | Chunk | Tuning | Tuning |
| CnN44 | Wikipedia | Text | Chunk | Tuning | Tuning |
| BOM26 | Wikipedia | Text | Chunk | Tuning | Tuning |
| CoL21 | Wikipedia | Text | Chunk | Tuning | Tuning |
| Take Elbassan22 | Wikipedia | Text | Chunk | Tuning | Tuning |
| PapeQA33 | Arxiv Online Dataset PubMed | Text | Chunk | Tuning | Tuning |
| NasaRAG34 | FactoidWiki | Text | Chunk | Tuning | Tuning |
| IAC15 | Search Engine Wikipedia | Text | Chunk | Tuning | Tuning |
| NoMBAACL16 | Wikipedia | Text | Chunk | Tuning | Tuning |
| ToC37 | Search Engine Wikipedia | Text | Chunk | Tuning | Tuning |
| SKR30 | Dataset-base, Wikipedia | Text | Chunk | Tuning | Tuning |
| ITRG32 | Wikipedia | Text | Chunk | Tuning | Tuning |
| RAG-LongContext30 | Dataset-base | Text | Chunk | Tuning | Tuning |
| ITER-BTIR31 | Dataset-base | Text | Chunk | Tuning | Tuning |
| IBCoT31 | Wikipedia | Text | Chunk | Tuning | Tuning |
| LLM-Knowledge Boundary32 | Wikipedia | Text | Chunk | Tuning | Tuning |
| RAPTOR16 | Dataset-base | Text | Chunk | Tuning | Tuning |
| RECITE22 | LLMs | Text | Chunk | Tuning | Tuning |
| ICRLM16 | Pile, Wikipedia | Text | Chunk | Tuning | Tuning |
| Retrieval-Sample16 | Dataset-base | Text | Doc | Tuning | Tuning |
| Zee30 | C4 | Text | Doc | Tuning | Tuning |
| CMA17 | Arxiv | Text | Doc | Tuning | Tuning |
| I-PAGER18 | Wikipedia | Text | Doc | Tuning | Tuning |
| PRCA18 | Dataset-base | Text | Doc | Tuning | Tuning |
| QML-Doc-ranking20 | Dataset-base | Text | Doc | Tuning | Tuning |
| Recompr17 | Wikipedia | Text | Doc | Tuning | Tuning |
| D9P21 | Pile | Text | Doc | Tuning | Tuning |
| ARALUX22 | Dataset-base | Text | Doc | Tuning | Tuning |
| ARABRAO17 | Dataset-base | Text | Doc | Tuning | Tuning |
| GenBank18 | LMG | Text | Doc | Tuning | Tuning |
| UnBhRAC11 | Dataset-base | Text | Doc | Tuning | Tuning |
| CREA4CL11 | Dataset-base | Text | Multi | Tuning | Tuning |
| PKG15 | LLM | Tableau Text | Chunk | Tuning | Tuning |
| SANTA16 | Dataset-base | Code, Text | Chunk | Tuning | Tuning |
| SURGE17 | Freebase | KG | Sub-Graph | Tuning | Tuning |
| KG-Tod17 | Dataset-base | KG | Entry | Tuning | Tuning |
| Dual-Book16 | Book | KG | Entry Sequence | Tuning | Tuning |
| KaawKaw15 | Dataset-base | KG | Entry Sequence | Tuning | Tuning |
| FABULA17 | Dataset-base | KG | Entry | Tuning | Tuning |
| HyKGE11 | CMuKG | KG | Entry | Tuning | Tuning |
| KALMV16 | Wikipedia | KG | Triple | Tuning | Tuning |
| RoL18 | Freebase | KG | Triple | Tuning | Tuning |
| G-Remover18 | Dataset-base | Text | Graph | Sub-Graph | Tuning |

## TABLE 1
SUMMARY OF RAG METHODS

Global search

• Most existing algorithms struggle with population level queries such as

• Who are the main competitors of company X?

• List all people who have worked with person X

• What does Paul graham generally write about?

• These queries require information from a large amount of chunks to be answered correctly

• More efficient ways of information representation are needed

GraphRAG

- Construct a graph on your dataset and query it using LLMs

- Natively supports population level queries, but construction is very expensive

# Triplex: SOTA LLM for Knowledge Graphs

| Entity Types | PERSON, ORGANIZATION |
|--------------|----------------------|
| RELATIONSHIPS | FOUNDED_BY           |
| TEXT          | Elon Musk is the founder of SpaceX |

<img src="Triplex" alt="Triplex logo"> Triplex &lt;/img&gt;

```json
{
  "entities_and_triples": [
    "[1], PERSON: Elon Musk",
    "[2], ORGANIZATION: SpaceX",
    "[2] FOUNDED_BY [1]"
  ]
}
```

- Better than GPT-4o and 97% cheaper
- Blog: https://www.sciphi.ai/blog/triplex
- Demo: https://kg.sciphi.ai

Benchmark

<img src="Bar chart showing benchmark comparison between gpt-3.5 (few-shot), gpt-4o (zero-shot), Triplex-tiny (zero-shot), gpt-4o (few-shot), and Triplex (zero-shot). The y-axis ranges from 0 to 0.6. The x-axis labels are: gpt-3.5 (few-shot), gpt-4o (zero-shot), Triplex-tiny (zero-shot), gpt-4o (few-shot), Triplex (zero-shot)." alt="Bar chart showing benchmark comparison between gpt-3.5 (few-shot), gpt-4o (zero-shot), Triplex-tiny (zero-shot), gpt-4o (few-shot), and Triplex (zero-shot). The y-axis ranges from 0 to 0.6. The x-axis labels are: gpt-3.5 (few-shot), gpt-4o (zero-shot), Triplex-tiny (zero-shot), gpt-4o (few-shot), Triplex (zero-shot).">

# Triplex: SOTA LLM for Knowledge Graphs

| Entity Types | PERSON, ORGANIZATION |
|--------------|----------------------|
| RELATIONSHIPS | FOUNDED_BY           |
| TEXT          | Elon Musk is the founder of SpaceX |

<img src="Triplex" alt="Triplex logo"> Triplex &lt;/img&gt;

```json
{
  "entities_and_triples": [
    "[1], PERSON: Elon Musk",
    "[2], ORGANIZATION: SpaceX",
    "[2] FOUNDED_BY [1]"
  ]
}
```

- Better than GPT-4o and 97% cheaper
- Blog: https://www.sciphi.ai/blog/triplex
- Demo: https://kg.sciphi.ai

Benchmark

<img src="Bar chart showing benchmark comparison between gpt-3.5 (few-shot), gpt-4o (zero-shot), Triplex-tiny (zero-shot), gpt-4o (few-shot), and Triplex (zero-shot). The y-axis ranges from 0 to 0.6. The x-axis labels are: gpt-3.5 (few-shot), gpt-4o (zero-shot), Triplex-tiny (zero-shot), gpt-4o (few-shot), Triplex (zero-shot)." alt="Bar chart showing benchmark comparison between gpt-3.5 (few-shot), gpt-4o (zero-shot), Triplex-tiny (zero-shot), gpt-4o (few-shot), and Triplex (zero-shot). The y-axis ranges from 0 to 0.6. The x-axis labels are: gpt-3.5 (few-shot), gpt-4o (zero-shot), Triplex-tiny (zero-shot), gpt-4o (few-shot), Triplex (zero-shot).">