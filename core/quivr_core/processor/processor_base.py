import logging
from abc import ABC, abstractmethod
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Generic, List, TypeVar

from attr import dataclass
from langchain_core.documents import Document

from quivr_core.files.file import FileExtension, QuivrFile
from quivr_core.language.utils import detect_language

logger = logging.getLogger("quivr_core")


R = TypeVar("R", covariant=True)


@dataclass
class ProcessedDocument(Generic[R]):
    chunks: List[Document]
    processor_cls: str
    processor_response: R


# TODO: processors should be cached somewhere ?
# The processor should be cached by processor type
# The cache should use a single
class ProcessorBase(ABC, Generic[R]):
    supported_extensions: list[FileExtension | str]

    def check_supported(self, file: QuivrFile) -> None:
        if file.file_extension not in self.supported_extensions:
            raise ValueError(f"can't process a file of type {file.file_extension}")

    @property
    @abstractmethod
    def processor_metadata(self) -> dict[str, Any]:
        raise NotImplementedError

    async def process_file(self, file: QuivrFile) -> ProcessedDocument[R]:
        logger.debug(f"Processing file {file}")
        self.check_supported(file)
        docs = await self.process_file_inner(file)
        try:
            qvr_version = version("quivr-core")
        except PackageNotFoundError:
            qvr_version = "dev"

        for idx, doc in enumerate(docs.chunks, start=1):
            if "original_file_name" in doc.metadata:
                doc.page_content = f"Filename: {doc.metadata['original_file_name']} Content: {doc.page_content}"
            doc.page_content = doc.page_content.replace("\u0000", "")
            doc.page_content = doc.page_content.encode("utf-8", "replace").decode(
                "utf-8"
            )
            doc.metadata = {
                "chunk_index": idx,
                "quivr_core_version": qvr_version,
                "language": detect_language(
                    text=doc.page_content.replace("\\n", " ").replace("\n", " "),
                    low_memory=True,
                ).value,
                **file.metadata,
                **doc.metadata,
                **self.processor_metadata,
            }
        return docs

    @abstractmethod
    async def process_file_inner(self, file: QuivrFile) -> ProcessedDocument[R]:
        raise NotImplementedError
