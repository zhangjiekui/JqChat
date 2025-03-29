from .abstractions import R2RProviders
from .api import *
from .app import *
from .app import R2RApp


# from .app_entry import r2r_app
from .assembly import *
from .orchestration import *
from .services import *

from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

__all__ = [
    # R2R Primary
    "R2RProviders",
    "R2RApp",
    "R2RBuilder",
    "R2RConfig",
    # Factory
    "R2RProviderFactory",
    ## R2R SERVICES
    "AuthService",
    "IngestionService",
    "ManagementService",
    "RetrievalService",
    "GraphService",
]

logger.debug("===============/data/projects/JqChatV2/JqChat/JqR2R/py/core/main/__init__.py中包括的包")
logger.debug(dir())
logger.debug("===============/data/projects/JqChatV2/JqChat/JqR2R/py/core/main/__init__.py中包括的包")
