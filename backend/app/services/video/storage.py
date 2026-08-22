"""Replaceable local storage for uploaded media."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fastapi import UploadFile


class FileTooLargeError(ValueError):
    """Raised when a streamed upload exceeds its configured limit."""


@dataclass(frozen=True)
class StoredFile:
    """Server-owned location and size of a stored upload."""

    path: Path
    size: int


class StorageService(Protocol):
    """Interface for storing and removing server-owned upload files."""

    async def save(self, upload: UploadFile, filename: str, max_size: int) -> StoredFile: ...
    def write_bytes(self, relative_path: Path, content: bytes) -> Path: ...
    def delete(self, path: Path) -> None: ...


class LocalStorageService:
    """Store uploads under a local directory using server-generated names."""

    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path

    async def save(self, upload: UploadFile, filename: str, max_size: int) -> StoredFile:
        self.root_path.mkdir(parents=True, exist_ok=True)
        destination = self.root_path / filename
        total_size = 0
        try:
            with destination.open("xb") as output:
                while chunk := await upload.read(1024 * 1024):
                    total_size += len(chunk)
                    if total_size > max_size:
                        raise FileTooLargeError("The uploaded video exceeds the maximum file size.")
                    output.write(chunk)
        except Exception:
            self.delete(destination)
            raise
        return StoredFile(path=destination, size=total_size)

    def delete(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def write_bytes(self, relative_path: Path, content: bytes) -> Path:
        """Write a processing artifact below the controlled storage root."""
        destination = self.root_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return destination

    def artifact_path(self, relative_path: Path) -> Path:
        """Reserve a server-controlled path for an external tool's output."""
        destination = self.root_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination
