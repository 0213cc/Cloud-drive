"""
文件去重客户端
提供文件去重相关功能
"""
import hashlib
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class DeduplicationClient:
    """文件去重客户端"""
    
    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """
        计算文件的SHA-256哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件的SHA-256哈希值（十六进制字符串）
        """
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            # 分块读取文件，避免大文件占用过多内存
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    @staticmethod
    def check_duplicate(
        session,
        base_url: str,
        hash_value: str,
        file_size: int,
        headers: dict
    ) -> Optional[Dict]:
        """
        检查文件是否已存在于服务器
        
        Args:
            session: requests会话
            base_url: API基础URL
            hash_value: 文件哈希值
            file_size: 文件大小
            headers: 请求头（包含认证信息）
            
        Returns:
            如果文件存在，返回文件块信息；否则返回None
        """
        url = f"{base_url}/api/deduplication/check"
        
        try:
            response = session.post(
                url,
                json={
                    'hash_value': hash_value,
                    'size': file_size
                },
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('exists'):
                    logger.info(
                        f"文件已存在: hash={hash_value[:16]}..., "
                        f"chunk_id={result.get('chunk_id')}, "
                        f"refs={result.get('reference_count')}"
                    )
                    return result
                else:
                    logger.info(f"文件不存在，需要上传: hash={hash_value[:16]}...")
                    return None
            else:
                logger.warning(f"检查重复文件失败: {response.status_code}, {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"检查重复文件异常: {e}")
            return None
    
    @staticmethod
    def upload_by_reference(
        session,
        base_url: str,
        filename: str,
        remote_path: str,
        chunk_id: int,
        file_size: int,
        hash_value: str,
        content_type: Optional[str],
        headers: dict
    ) -> Dict:
        """
        通过引用已存在的文件块上传文件
        
        Args:
            session: requests会话
            base_url: API基础URL
            filename: 文件名
            remote_path: 远程路径
            chunk_id: 文件块ID
            file_size: 文件大小
            hash_value: 文件哈希值
            content_type: 文件类型
            headers: 请求头
            
        Returns:
            上传结果
        """
        url = f"{base_url}/api/files/upload-by-reference"
        
        params = {
            'filename': filename,
            'path': remote_path,
            'chunk_id': chunk_id,
            'size': file_size,
            'hash_value': hash_value
        }
        
        if content_type:
            params['content_type'] = content_type
        
        try:
            response = session.post(url, params=params, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"通过去重上传成功: {filename}")
                return {
                    'success': True,
                    'result': result,
                    'deduplicated': True
                }
            else:
                error_msg = response.json().get('detail', '未知错误')
                logger.error(f"通过去重上传失败: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'deduplicated': False
                }
                
        except Exception as e:
            logger.error(f"通过去重上传异常: {e}")
            return {
                'success': False,
                'error': str(e),
                'deduplicated': False
            }
    
    @staticmethod
    def get_deduplication_stats(
        session,
        base_url: str,
        headers: dict
    ) -> Optional[Dict]:
        """
        获取去重统计信息
        
        Args:
            session: requests会话
            base_url: API基础URL
            headers: 请求头
            
        Returns:
            去重统计信息
        """
        url = f"{base_url}/api/deduplication/stats"
        
        try:
            response = session.get(url, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"获取去重统计失败: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"获取去重统计异常: {e}")
            return None

