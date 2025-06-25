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
- **Native RAG**
- **Advanced RAG**
- **DSP (e.g. 09/23/21)**
- **1ER-0E12EN (Date of Use)**

### Methods

| Method | Retrieval Source | Retrieval Data Type | Retrieval Granularity | Augmentation Stage | Retrieval Process |
|--------|------------------|--------------------|-----------------------|------------------|------------------|
| CGL1 [26] | Wikipedia       | Text               | Phrase                | Pre-training      | Iterative         |
| DenaX [27] | FactoidWiki     | Text               | Posponizer           | Tuning            | Tuning            |
| EAR [31]  | Dataset-base    | Text               | Sentence              | Tuning            | Tuning            |
| UPISE [28] | Dataset-base    | Text               | Sentence              | Tuning            | Tuning            |
| RAST [32]  | Dataset-base    | Text               | Sentence              | Tuning            | Tuning            |
| SaIF4em [33] | Dataset-base    | Text               | Sentence              | Tuning            | Tuning            |
| FLARE [34] | Search Engine Wiki | Text               | Sentence              | Tuning            | Tuning            |
| PGRB [35]  | Wikipedia        | Text               | Sentence              | Tuning            | Tuning            |
| FLLYU [36] | Wikipedia        | Text               | Sentence              | Tuning            | Tuning            |
| RADIA [37] | Dataset-base    | Text               | Sentence              | Tuning            | Tuning            |
| Filter error [38] | Synthesized dataset | Text               | Sentence              | Tuning            | Tuning            |
| R-QQA [39] | Dataset-base    | Text               | Sentence Pair         | Tuning            | Tuning            |
| LLM-R [39] | Dataset-base    | Text               | Sentence              | Tuning            | Tuning            |
| TIGER [40] | Dataset-base    | Text               | Item-base             | Pre-training      | Tuning            |
| LM-baker [41] | Dataset-base    | Text               | Item-base             | Tuning            | Tuning            |
| BEEQE [42] | Dataset-base    | Text               | Item-base             | Tuning            | Tuning            |
| CV-RAI [43] | Synthesized dataset | Text               | Item-base             | Tuning            | Tuning            |
| Atea [44]  | Wikipedia        | Text               | Chunk                 | Pre-training      | Iterative         |
| RAVEN [45] | Wikipedia        | Text               | Chunk                 | Pre-training      | Iterative         |
| RETM0+ [46] | Pre-training Corpus | Text               | Chunk                 | Pre-training      | Iterative         |
| INSTRUCTIONER [47] | Pre-training corpus | Text               | Chunk                 | Tuning            | Tuning            |
| KRR [48]   | Search Engine | Text               | Chunk                 | Tuning            | Tuning            |
| RA-DA [49] | Dataset-base    | Text               | Chunk                 | Tuning            | Tuning            |
| PROMPTAGATOR [50] | BERT | Text               | Chunk                 | Tuning            | Tuning            |
| AAE [51]   | MENTION, Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| RA-XT [52] | Common Corpus, Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| RAG-Robots [53] | Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| RA-Lang Form [54] | Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| CnN [55]   | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| Scf-A4G [56] | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| BOM [57]   | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| CoL [58]   | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| Take Elitism [59] | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| PopqQA [60] | Arxiv, Online, Database, PubMed | Text               | Chunk                 | Tuning            | Tuning            |
| NasaQa [61] | FactoidWiki      | Text               | Chunk                 | Tuning            | Tuning            |
| NoMBAACL [62] | Search Engine, Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| ToC [63]   | Search Engine, Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| SkR [64]   | Dataset-base, Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| ITRG [65]  | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| RAG-Long Context [66] | Dataset-base | Text               | Chunk                 | Tuning            | Tuning            |
| ITER-BTIRAS [67] | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| IBCoT [68] | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| LLM-Knowledge Boundary [69] | Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| RAPTOR [70] | Dataset-base    | Text               | Chunk                 | Tuning            | Tuning            |
| RECTIE [71] | LLMs | Text               | Doc                  | Tuning            | Tuning            |
| ICRLM [72] | Pile, Wikipedia | Text               | Doc                  | Tuning            | Tuning            |
| Retrieval Sample [73] | Dataset-base | Text               | Doc                  | Tuning            | Tuning            |
| Zeez [74]   | C4 | Text               | Doc                  | Tuning            | Tuning            |
| CMA [75]   | Arxiv | Text               | Doc                  | Tuning            | Tuning            |
| I-PAGER [76] | Wikipedia        | Text               | Doc                  | Tuning            | Tuning            |
| PRCA [77]   | Dataset-base    | Text               | Doc                  | Tuning            | Tuning            |
| QML-Doc-ranking [78] | Dataset-base | Text               | Doc                  | Tuning            | Tuning            |
| Recompr [79] | Wikipedia        | Text               | Doc                  | Tuning            | Tuning            |
| D9P [80]   | Wikipedia        | Text               | Doc                  | Tuning            | Tuning            |
| ARABAAO [81] | Dataset-base    | Text               | Doc                  | Tuning            | Tuning            |
| GenBank [82] | LLMs | Text               | Doc                  | Tuning            | Tuning            |
| UnbN-RAIC [83] | Dataset-base | Text               | Doc                  | Tuning            | Tuning            |
| CREA-ACL [114] | Dataset-base | Text               | Doc                  | Tuning            | Tuning            |
| PKG [85]   | LLM | Text               | Doc                  | Tuning            | Tuning            |
| SANTA [86]  | Dataset-base    | Text               | Doc                  | Tuning            | Tuning            |
| SURGE [87]  | Freebase        | KG                 | Sub-Graph            | Tuning            | Tuning            |
| KG-Tool [88] | Dataset-base    | KG                 | Entry                | Tuning            | Tuning            |
| Dual-Book [89] | Wikipedia, Dataset-base | KG                 | Entry                | Tuning            | Tuning            |
| KaanKoala [90] | Dataset-base, OpenAI | KG                 | Entry                | Tuning            | Tuning            |
| FABULA [91] | Dataset-base, OpenAI | KG                 | Entry                | Tuning            | Tuning            |
| HyKGE [92]  | CMuKG | KG                 | Entry                | Tuning            | Tuning            |
| KALMV [93]  | Wikipedia        | KG                 | Triplet              | Tuning            | Tuning            |
| RoL [94]   | Freebase        | KG                 | Triplet              | Tuning            | Tuning            |
| G-Remover [95] | Dataset-base | KG                 | Triplet              | Tuning            | Tuning            |

## TABLE 1
SUMMARY OF RAG METHODS

| Method | Retrieval Source | Retrieval Data Type | Retrieval Granularity | Augmentation Stage | Retrieval Process |
|--------|------------------|--------------------|-----------------------|------------------|------------------|
| CGL1 [26] | Wikipedia       | Text               | Phrase                | Pre-training      | Iterative         |
| DenaX [27] | FactoidWiki     | Text               | Posponizer           | Tuning            | Tuning            |
| EAR [31]  | Dataset-base    | Text               | Sentence              | Tuning            | Tuning            |
| UPISE [28] | Dataset-base    | Text               | Sentence              | Tuning            | Tuning            |
| RAST [32]  | Dataset-base    | Text               | Sentence              | Tuning            | Tuning            |
| SaIF4em [33] | Dataset-base    | Text               | Sentence              | Tuning            | Tuning            |
| FLARE [34] | Search Engine Wiki | Text               | Sentence              | Tuning            | Tuning            |
| PGRB [35]  | Wikipedia        | Text               | Sentence              | Tuning            | Tuning            |
| FLLYU [36] | Wikipedia        | Text               | Sentence              | Tuning            | Tuning            |
| RADIA [37] | Dataset-base    | Text               | Sentence              | Tuning            | Tuning            |
| Filter error [38] | Synthesized dataset | Text               | Sentence              | Tuning            | Tuning            |
| R-QQA [39] | Dataset-base    | Text               | Sentence Pair         | Tuning            | Tuning            |
| LLM-R [39] | Dataset-base    | Text               | Sentence              | Tuning            | Tuning            |
| TIGER [40] | Dataset-base    | Text               | Item-base             | Pre-training      | Tuning            |
| LM-baker [41] | Dataset-base    | Text               | Item-base             | Tuning            | Tuning            |
| BEEQE [42] | Dataset-base    | Text               | Item-base             | Tuning            | Tuning            |
| CV-RAI [43] | Synthesized dataset | Text               | Item-base             | Tuning            | Tuning            |
| Atea [44]  | Wikipedia        | Text               | Chunk                 | Pre-training      | Iterative         |
| RAVEN [45] | Wikipedia        | Text               | Chunk                 | Pre-training      | Iterative         |
| RETM0+ [46] | Pre-training Corpus | Text               | Chunk                 | Pre-training      | Iterative         |
| INSTRUCTIONER [47] | Pre-training corpus | Text               | Chunk                 | Tuning            | Tuning            |
| KRR [48]   | Search Engine | Text               | Chunk                 | Tuning            | Tuning            |
| RA-DA [49] | Dataset-base    | Text               | Chunk                 | Tuning            | Tuning            |
| PROMPTAGATOR [50] | BERT | Text               | Chunk                 | Tuning            | Tuning            |
| AAE [51]   | MENTION, Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| RA-XT [52] | Common Corpus, Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| RAG-Robots [53] | Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| RA-Lang Form [54] | Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| CnN [55]   | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| Scf-A4G [56] | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| BOM [57]   | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| CoL [58]   | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| Take Elitism [59] | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| PopqQA [60] | Arxiv, Online, Database, PubMed | Text               | Chunk                 | Tuning            | Tuning            |
| NasaQa [61] | FactoidWiki      | Text               | Chunk                 | Tuning            | Tuning            |
| NoMBAACL [62] | Search Engine, Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| ToC [63]   | Search Engine, Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| SkR [64]   | Dataset-base, Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| ITRG [65]  | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| RAG-Long Context [66] | Dataset-base | Text               | Chunk                 | Tuning            | Tuning            |
| ITER-BTIRAS [67] | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| IBCoT [68] | Wikipedia        | Text               | Chunk                 | Tuning            | Tuning            |
| LLM-Knowledge Boundary [69] | Wikipedia | Text               | Chunk                 | Tuning            | Tuning            |
| RAPTOR [70] | Dataset-base    | Text               | Chunk                 | Tuning            | Tuning            |
| RECTIE [71] | LLMs | Text               | Doc                  | Tuning            | Tuning            |
| ICRLM [72] | Pile, Wikipedia | Text               | Doc                  | Tuning            | Tuning            |
| Retrieval Sample [73] | Dataset-base | Text               | Doc                  | Tuning            | Tuning            |
| Zeez [74]   | C4 | Text               | Doc                  | Tuning            | Tuning            |
| CMA [75]   | Arxiv | Text               | Doc                  | Tuning            | Tuning            |
| I-PAGER [76] | Wikipedia        | Text               | Doc                  | Tuning            | Tuning            |
| PRCA [77]   | Dataset-base    | Text               | Doc                  | Tuning            | Tuning            |
| QML-Doc-ranking [78] | Dataset-base | Text               | Doc                  | Tuning            | Tuning            |
| Recompr [79] | Wikipedia        | Text               | Doc                  | Tuning            | Tuning            |
| D9P [80]   | Wikipedia        | Text               | Doc                  | Tuning            | Tuning            |
| ARABAAO [81] | Dataset-base    | Text               | Doc                  | Tuning            | Tuning            |
| GenBank [82] | LLMs | Text               | Doc                  | Tuning            | Tuning            |
| UnbN-RAIC [83] | Dataset-base | Text               | Doc                  | Tuning            | Tuning            |
| CREA-ACL [114] | Dataset-base | Text               | Doc                  | Tuning            | Tuning            |
| PKG [85]   | LLM | Text               | Doc                  | Tuning            | Tuning            |
| SANTA [86]  | Dataset-base    | Text               | Doc                  | Tuning            | Tuning            |
| SURGE [87]  | Freebase        | KG                 | Sub-Graph            | Tuning            | Tuning            |
| KG-Tool [88] | Dataset-base    | KG                 | Entry                | Tuning            | Tuning            |
| Dual-Book [89] | Wikipedia, Dataset-base | KG                 | Entry                | Tuning            | Tuning            |
| KaanKoala [90] | Dataset-base, OpenAI | KG                 | Entry                | Tuning            | Tuning            |
| FABULA [91] | Dataset-base, OpenAI | KG                 | Entry                | Tuning            | Tuning            |
| HyKGE [92]  | CMuKG | KG                 | Entry                | Tuning            | Tuning            |
| KALMV [93]  | Wikipedia        | KG                 | Triplet              | Tuning            | Tuning            |
| RoL [94]   | Freebase        | KG                 | Triplet              | Tuning            | Tuning            |
| G-Remover [95] | Dataset-base | KG                 | Triplet              | Tuning            | Tuning            |

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