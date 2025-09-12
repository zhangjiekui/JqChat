import os,sys,pathlib
project_root_path = pathlib.Path().resolve()
sys.path.append(str(project_root_path))
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()
logger.warning(f"已在JqR2R/py/r2r/__init__.py文件中直接将{project_root_path}添加到sys.path中")
from sdk import *
from shared import *
from core.utils.logging_config import configure_logging
from jqcode.jq_agent.c0_init_env_models import env_models_instance
from jqcode.jq_utils.logger import jqkj_logger

from importlib import metadata
from sdk.async_client import R2RAsyncClient
from sdk.sync_client import R2RClient
from core import *
from core.providers.embeddings.litellm import LiteLLMEmbeddingProvider
from core.providers.llm.litellm import LiteLLMCompletionProvider



logger = jqkj_logger(__file__).get_logger()

__version__ = metadata.version("r2r")
logger.debug("===============/data/projects/JqChatV2/JqChat/JqR2R/py/r2r/__init__.py中包括的包")
logger.debug(dir())
logger.debug("===============/data/projects/JqChatV2/JqChat/JqR2R/py/r2r/__init__.py中包括的包")
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
