from importlib import metadata

from sdk.async_client import R2RAsyncClient
from sdk.sync_client import R2RClient
from core import *
from core.providers.embeddings.litellm import LiteLLMEmbeddingProvider
from core.providers.llm.litellm import LiteLLMCompletionProvider

from sdk import *
from shared import *
from core.utils.logging_config import configure_logging

__version__ = metadata.version("r2r")
print("===============/data/projects/JqChatV2/JqChat/JqR2R/py/r2r/__init__.py中包括的包")
print(dir())
print("===============/data/projects/JqChatV2/JqChat/JqR2R/py/r2r/__init__.py中包括的包")
# __all__ = [
#     # "R2RApp",
#     "R2RBuilder",
#     "R2RConfig",
#     "R2RProviderFactory",
#     "R2RAsyncClient",
#     "R2RClient",
#     "__version__",
#     "R2RException",
# ]
# print(__all__)
def get_version():
    return __version__
