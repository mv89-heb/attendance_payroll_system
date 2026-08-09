import os
import uuid
from abc import ABC, abstractmethod

class FileStorageService(ABC):
    @abstractmethod
    def save(self, file_data: bytes, filename: str) -> str:
        pass

    @abstractmethod
    def get(self, file_path: str) -> bytes:
        pass

    @abstractmethod
    def delete(self, file_path: str) -> bool:
        pass

    @abstractmethod
    def exists(self, file_path: str) -> bool:
        pass

class LocalFileStorageService(FileStorageService):
    def __init__(self, upload_dir: str):
        self.upload_dir = upload_dir
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir, exist_ok=True)

    def save(self, file_data: bytes, filename: str) -> str:
        file_uuid = str(uuid.uuid4())
        _, ext = os.path.splitext(filename)
        unique_name = f"{file_uuid}{ext}"
        file_path = os.path.join(self.upload_dir, unique_name)
        with open(file_path, "wb") as f:
            f.write(file_data)
        return file_path

    def get(self, file_path: str) -> bytes:
        if not self.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(file_path, "rb") as f:
            return f.read()

    def delete(self, file_path: str) -> bool:
        if self.exists(file_path):
            os.remove(file_path)
            return True
        return False

    def exists(self, file_path: str) -> bool:
        return os.path.exists(file_path)
