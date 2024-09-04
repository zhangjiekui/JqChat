from abc import ABC, abstractmethod
from typing import List, Optional, Union
from langchain.schema import Document

class JqBaseDocumentStore(ABC):
    """A document store is in charged of storing and managing documents"""

    @abstractmethod
    def __init__(self, *args, **kwargs):
        self.count = self._count()
        self.ids = self._ids()
        ...

    @abstractmethod
    def add_or_update_index_metadata_if_id_exists(
        self,
        docs: Union[Document, List[Document]],
        ids: Optional[Union[List[str], str]] = None,
        **kwargs,
    ):
        """Add document into document store

        Args:
            docs: Document or list of documents
            ids: List of ids of the documents. Optional, if not set will use doc.doc_id
        """
        ...

    @abstractmethod
    def get_docs_by_ids(self, ids: Union[List[str], str]) -> List[Document]:
        """Get document by id"""
        ...

    @abstractmethod
    def get_all_docs(self) -> List[Document]:
        """Get all documents"""
        ...

    @abstractmethod
    def _count(self) -> int:
        """Count number of documents"""
        ...
    @abstractmethod
    def _ids(self) -> set[str]:
        """get all documents (Unique) ids, return the ids set """
        ...
    
    @abstractmethod
    def search_docs_by_text(self, user_query_text: str=None,top_k: int = 10, query_on_fileds:list =["file_name","file_text"],filter_by_doc_ids:list=None,filter_by_doc_types:list=None,filter_by_status:list=["true"]) -> List[Document]:
        """Search document store using search query"""
        ...

    @abstractmethod
    def delete(self, ids: Union[List[str], str]):
        """Delete document by id"""
        ...

    @abstractmethod
    def drop(self):
        """Drop the document store"""
        ...
    @abstractmethod    
    def get_settings_and_mappings(self):
        """return the index/store's settings and mappings"""
        ...