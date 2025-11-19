"""
断点续传客户端

封装与断点续传API的交互
"""
import requests
from typing import Dict, List

class ResumableUploadClient:
    """断点续传客户端"""

    @staticmethod
    def start_session(
        session: requests.Session,
        base_url: str,
        filename: str,
        path: str,
        total_size: int,
        file_hash: str,
        chunk_size: int,
        total_chunks: int,
        headers: Dict
    ) -> Dict:
        """开始或恢复一个上传会话"""
        url = f"{base_url}/api/resumable/start"
        data = {
            "filename": filename,
            "path": path,
            "total_size": total_size,
            "file_hash": file_hash,
            "chunk_size": chunk_size,
            "total_chunks": total_chunks
        }
        response = session.post(url, json=data, headers=headers)
        response.raise_for_status()  # 如果请求失败则抛出异常
        return response.json()

    @staticmethod
    def get_status(
        session: requests.Session,
        base_url: str,
        upload_id: str,
        headers: Dict
    ) -> Dict:
        """查询上传会话的状态"""
        url = f"{base_url}/api/resumable/status/{upload_id}"
        response = session.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def complete_session(
        session: requests.Session,
        base_url: str,
        upload_id: str,
        assemble_request: Dict,
        headers: Dict
    ) -> Dict:
        """完成上传会话并组装文件"""
        url = f"{base_url}/api/resumable/complete/{upload_id}"
        response = session.post(url, json=assemble_request, headers=headers)
        response.raise_for_status()
        return response.json()

