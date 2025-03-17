from importlib import metadata

from R2RV350.py.sdk.async_client import R2RAsyncClient
from R2RV350.py.sdk.models import (
    CitationEvent,
    FinalAnswerEvent,
    MessageEvent,
    R2RException,
    SearchResultsEvent,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from R2RV350.py.sdk.sync_client import R2RClient
from R2RV350.py.shared import *

# __version__ = metadata.version("r2r")
__version__ = '3.5.0'

__all__ = [
    "R2RAsyncClient",
    "R2RClient",
    "__version__",
    "R2RException",
    "CitationEvent",
    "ThinkingEvent",
    "ToolCallEvent",
    "ToolResultEvent",
    "FinalAnswerEvent",
    "MessageEvent",
    "SearchResultsEvent",
]


def get_version():
    return __version__
