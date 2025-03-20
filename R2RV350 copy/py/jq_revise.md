### Feature/make parsing chunking providers [https://github.com/SciPhi-AI/R2R/pull/820]

Summary:
Introduced chunking and parsing providers, updated configurations, and modified pipelines and tests to integrate new providers.

Key points:

Added ChunkingProvider and ParsingProvider classes in r2r/base/providers/chunking.py and r2r/base/providers/parsing.py.
Updated r2r.toml and pyproject.toml to include new chunking and parsing configurations.
Modified r2r/base/__init__.py to import new providers.
Created ChunkingPipe and ParsingPipe in r2r/pipes/ingestion.
Updated IngestionPipeline in r2r/pipelines/ingestion_pipeline.py to use new pipes.
Added R2RChunkingProvider and UnstructuredChunkingProvider in r2r/providers/chunking.
Added R2RParsingProvider and UnstructuredParsingProvider in r2r/providers/parsing.
Updated R2RConfig in r2r/main/assembly/config.py to handle new configurations.
Updated R2RProviderFactory in r2r/main/assembly/factory.py to create new providers.
Updated tests in tests/test_config.py to cover new configurations.

