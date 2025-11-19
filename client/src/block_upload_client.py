"""
块级上传客户端

支持文件分块上传和块级去重
"""
import hashlib
import os
from typing import List, Dict, Optional
import requests
from tqdm import tqdm
from resumable_client import ResumableUploadClient


class BlockInfo:
    """数据块信息"""
    def __init__(self, data: bytes, offset: int, index: int):
        self.data = data
        self.offset = offset
        self.index = index
        self.size = len(data)
        self.hash_value = hashlib.sha256(data).hexdigest()


class BlockUploadClient:
    """块级上传客户端"""
    
    # 默认块大小：4MB
    DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024
    
    @staticmethod
    def should_use_block_chunking(file_size: int, chunk_size: int = None) -> bool:
        """
        判断是否应该使用块级去重
        
        对于小文件（小于2倍块大小），使用文件级去重更高效
        对于大文件，使用块级去重可以提高去重效率
        """
        if chunk_size is None:
            chunk_size = BlockUploadClient.DEFAULT_CHUNK_SIZE
        
        return file_size > (chunk_size * 2)
    
    @staticmethod
    def chunk_file_fixed(file_path: str, chunk_size: int = None) -> List[BlockInfo]:
        """
        固定大小分块
        
        Args:
            file_path: 文件路径
            chunk_size: 块大小（字节）
        
        Returns:
            数据块列表
        """
        if chunk_size is None:
            chunk_size = BlockUploadClient.DEFAULT_CHUNK_SIZE
        
        chunks = []
        offset = 0
        index = 0
        
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                
                chunk = BlockInfo(data, offset, index)
                chunks.append(chunk)
                
                offset += len(data)
                index += 1
        
        return chunks
    
    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """
        计算文件哈希值
        
        Args:
            file_path: 文件路径
        
        Returns:
            SHA-256哈希值
        """
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(8192)
                if not data:
                    break
                sha256.update(data)
        
        return sha256.hexdigest()
    
    @staticmethod
    def check_blocks(
        session: requests.Session,
        base_url: str,
        hash_values: List[str],
        headers: Dict
    ) -> Dict:
        """
        检查哪些数据块已存在
        
        Args:
            session: requests会话
            base_url: API基础URL
            hash_values: 数据块哈希值列表
            headers: 请求头
        
        Returns:
            检查结果
        """
        url = f"{base_url}/api/block-upload/check-blocks"
        
        response = session.post(
            url,
            json={"hash_values": hash_values},
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"检查数据块失败: {response.status_code} - {response.text}")
    
    @staticmethod
    def upload_block(
        session: requests.Session,
        base_url: str,
        block: BlockInfo,
        upload_id: Optional[str],
        enable_compression: bool,
        headers: Dict,
        show_progress: bool = False
    ) -> Dict:
        """
        上传单个数据块
        
        Args:
            session: requests会话
            base_url: API基础URL
            block: 数据块信息
            enable_compression: 是否启用压缩
            headers: 请求头
            show_progress: 是否显示进度
        
        Returns:
            上传结果
        """
        url = f"{base_url}/api/block-upload/upload-block"
        
        params = {
            "block_hash": block.hash_value,
            "block_index": block.index,
            "enable_compression": enable_compression
        }
        if upload_id:
            params["upload_id"] = upload_id
        
        files = {
            "file": (f"block_{block.index}", block.data, "application/octet-stream")
        }
        
        # 移除Content-Type头，让requests自动设置multipart/form-data
        upload_headers = {k: v for k, v in headers.items() if k.lower() != 'content-type'}
        
        response = session.post(
            url,
            params=params,
            files=files,
            headers=upload_headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"上传数据块失败: {response.status_code} - {response.text}")
    
    @staticmethod
    def assemble_file(
        session: requests.Session,
        base_url: str,
        filename: str,
        path: str,
        content_type: Optional[str],
        total_size: int,
        file_hash: str,
        chunking_algorithm: str,
        chunk_size: int,
        blocks: List[BlockInfo],
        headers: Dict
    ) -> Dict:
        """
        组装文件
        
        Args:
            session: requests会话
            base_url: API基础URL
            filename: 文件名
            path: 远程路径
            content_type: 内容类型
            total_size: 文件总大小
            file_hash: 文件哈希值
            chunking_algorithm: 分块算法
            chunk_size: 块大小
            blocks: 数据块列表
            headers: 请求头
        
        Returns:
            组装结果
        """
        url = f"{base_url}/api/block-upload/assemble"
        
        blocks_info = [
            {
                "hash": block.hash_value,
                "index": block.index,
                "offset": block.offset,
                "size": block.size
            }
            for block in blocks
        ]
        
        data = {
            "filename": filename,
            "path": path,
            "content_type": content_type,
            "total_size": total_size,
            "file_hash": file_hash,
            "chunking_algorithm": chunking_algorithm,
            "chunk_size": chunk_size,
            "blocks": blocks_info
        }
        
        response = session.post(
            url,
            json=data,
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"组装文件失败: {response.status_code} - {response.text}")
    
    @staticmethod
    def upload_file_with_blocks(
        session: requests.Session,
        base_url: str,
        file_path: str,
        remote_path: str = "/",
        headers: Dict = None,
        chunk_size: int = None,
        chunking_algorithm: str = "fixed",
        enable_compression: bool = True,
        show_progress: bool = True,
        enable_resumable: bool = True
    ) -> Dict:
        """
        使用块级去重上传文件
        
        Args:
            session: requests会话
            base_url: API基础URL
            file_path: 本地文件路径
            remote_path: 远程目录路径
            headers: 请求头
            chunk_size: 块大小（字节）
            chunking_algorithm: 分块算法
            enable_compression: 是否启用压缩
            show_progress: 是否显示进度
        
        Returns:
            上传结果
        """
        if headers is None:
            headers = {}
        
        if chunk_size is None:
            chunk_size = BlockUploadClient.DEFAULT_CHUNK_SIZE
        
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        print(f"\n=== 块级上传: {filename} ({file_size / 1024 / 1024:.2f} MB) ===")
        
        # 1. 计算文件哈希
        if show_progress:
            print("计算文件哈希...")
        file_hash = BlockUploadClient.calculate_file_hash(file_path)
        
        # 2. 分块
        if show_progress:
            print(f"分块文件（块大小: {chunk_size / 1024 / 1024:.2f} MB）...")
        chunks = BlockUploadClient.chunk_file_fixed(file_path, chunk_size)
        print(f"✓ 文件已分成 {len(chunks)} 个数据块")
        
        upload_id = None
        uploaded_chunks_indices = set()

        # 3. 检查服务器上已存在的数据块（跨文件去重）
        print("检查数据块去重...")
        hash_values = [chunk.hash_value for chunk in chunks]
        check_result = BlockUploadClient.check_blocks(session, base_url, hash_values, headers)
        existing_hashes = set(check_result['existing_blocks'].keys())

        if enable_resumable:
            print("启动或恢复上传会话...")
            try:
                session_info = ResumableUploadClient.start_session(
                    session, base_url, filename, remote_path, file_size,
                    file_hash, chunk_size, len(chunks), headers
                )
                upload_id = session_info['upload_id']
                uploaded_chunks_indices = set(session_info.get('uploaded_chunks', []))
                print(f"✓ {session_info['message']}: upload_id={upload_id}")
                if uploaded_chunks_indices:
                    print(f"✓ 会话中已上传 {len(uploaded_chunks_indices)}/{len(chunks)} 个数据块")

            except Exception as e:
                print(f"✗ 启动上传会话失败: {e}. 将禁用断点续传。")
                enable_resumable = False
        
        # 4. 确定需要上传的数据块（结合去重和断点续传）
        chunks_to_upload = []
        for chunk in chunks:
            # 如果数据块的哈希值不存在于服务器，并且其索引也不在已上传的块中，则需要上传
            if chunk.hash_value not in existing_hashes and chunk.index not in uploaded_chunks_indices:
                chunks_to_upload.append(chunk)

        dedup_count = len(chunks) - len(chunks_to_upload)
        upload_count = len(chunks_to_upload)
        print(f"✓ 已存在: {dedup_count} 个块, 需上传: {upload_count} 个块")

        if dedup_count > 0 and len(chunks) > 0:
            dedup_ratio = int(dedup_count / len(chunks) * 100)
            print(f"✓ 去重率: {dedup_ratio}%")

        # 4. 上传缺失的数据块
        if upload_count > 0:
            if show_progress:
                print(f"\n上传数据块...")
                progress_bar = tqdm(
                    total=upload_count,
                    unit='块',
                    desc="上传进度"
                )
            
            for chunk in chunks_to_upload:
                try:
                    result = BlockUploadClient.upload_block(
                        session, base_url, chunk, upload_id,
                        enable_compression, headers, show_progress=False
                    )
                    if show_progress:
                        progress_bar.update(1)
                        if result.get('compressed'):
                            ratio = result.get('compression_ratio', 0)
                            progress_bar.set_postfix({'压缩': f"{ratio}%"})
                except Exception as e:
                    if show_progress: progress_bar.close()
                    raise Exception(f"上传数据块 {chunk.index} 失败: {e}")
            
            if show_progress: progress_bar.close()
            print(f"✓ 已上传 {upload_count} 个数据块")
        else:
            print("✓ 所有数据块都已存在，无需上传")
        
        # 5. 组装文件
        if show_progress:
            print("\n组装文件...")
        
        import mimetypes
        content_type, _ = mimetypes.guess_type(filename)
        
        blocks_info = [{"hash": c.hash_value, "index": c.index, "offset": c.offset, "size": c.size} for c in chunks]
        assemble_request_data = {
            "filename": filename, "path": remote_path, "content_type": content_type,
            "total_size": file_size, "file_hash": file_hash, "chunking_algorithm": chunking_algorithm,
            "chunk_size": chunk_size, "blocks": blocks_info
        }

        if enable_resumable and upload_id:
            result = ResumableUploadClient.complete_session(
                session, base_url, upload_id, assemble_request_data, headers
            )
        else:
            result = BlockUploadClient.assemble_file(
                session, base_url, filename, remote_path, content_type,
                file_size, file_hash, chunking_algorithm, chunk_size, chunks, headers
            )
        
        if result.get('success'):
            print(f"✓ {result['message']}")
            if result.get('deduplication_stats'):
                stats = result['deduplication_stats']
                print(f"  - 总块数: {stats['total_blocks']}")
                print(f"  - 唯一块数: {stats['unique_blocks']}")
                print(f"  - 去重率: {stats['deduplication_ratio']}%")
            
            return {
                "success": True, "file_id": result.get('file_id'),
                "version": result.get('version'), "message": result['message'],
                "deduplication_stats": result.get('deduplication_stats')
            }
        else:
            raise Exception(f"组装文件失败: {result.get('message', '未知错误')}")

