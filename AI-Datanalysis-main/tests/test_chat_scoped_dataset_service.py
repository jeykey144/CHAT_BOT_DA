from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from ai_datanalysis.services import dataset_service


class _UploadedFile:
    def __init__(self, name: str, content: bytes):
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


def test_chat_scoped_manifests_are_isolated():
    original_upload_dir = dataset_service.UPLOAD_DIR
    try:
        with TemporaryDirectory() as tmp:
            dataset_service.UPLOAD_DIR = Path(tmp)
            user = "alice"

            file_a = _UploadedFile("sales.csv", b"id,value\n1,10\n2,20\n")
            file_b = _UploadedFile("inventory.csv", b"id,stock\n1,5\n2,8\n")

            paths_a = dataset_service.save_uploaded_files(user, [file_a], chat_id="chat-a")
            paths_b = dataset_service.save_uploaded_files(user, [file_b], chat_id="chat-b")

            manifest_a = dataset_service.load_saved_manifest(user, chat_id="chat-a")
            manifest_b = dataset_service.load_saved_manifest(user, chat_id="chat-b")

            assert manifest_a == paths_a
            assert manifest_b == paths_b
            assert manifest_a != manifest_b
            assert dataset_service.load_saved_manifest(user) == []
    finally:
        dataset_service.UPLOAD_DIR = original_upload_dir


def test_clear_saved_manifest_only_removes_target_chat():
    original_upload_dir = dataset_service.UPLOAD_DIR
    try:
        with TemporaryDirectory() as tmp:
            dataset_service.UPLOAD_DIR = Path(tmp)
            user = "alice"

            file_a = _UploadedFile("sales.csv", b"id,value\n1,10\n")
            file_b = _UploadedFile("inventory.csv", b"id,stock\n1,5\n")

            dataset_service.save_uploaded_files(user, [file_a], chat_id="chat-a")
            dataset_service.save_uploaded_files(user, [file_b], chat_id="chat-b")

            dataset_service.clear_saved_manifest(user, chat_id="chat-a")

            assert dataset_service.load_saved_manifest(user, chat_id="chat-a") == []
            assert dataset_service.load_saved_manifest(user, chat_id="chat-b") != []
    finally:
        dataset_service.UPLOAD_DIR = original_upload_dir
