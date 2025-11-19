"""
云盘客户端 - 用于测试后端API
"""
import requests
import os
import sys
from typing import Optional, Dict, List
from tqdm import tqdm
import json
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import config
from auth_client import AuthClient
from dedup_client import DeduplicationClient
from block_upload_client import BlockUploadClient


class CloudDriveClient:
    """云盘客户端"""
    
    def __init__(self, base_url: str = None, auth_client: AuthClient = None):
        """
        初始化客户端
        
        Args:
            base_url: API基础URL
            auth_client: 认证客户端（可选）
        """
        self.base_url = base_url or config.API_BASE_URL
        self.session = requests.Session()
        self.auth_client = auth_client or AuthClient(self.base_url)
    
    def _get_headers(self) -> dict:
        """
        获取请求头（包含认证信息）
        
        Returns:
            请求头字典
        """
        headers = {}
        
        # 如果已认证，添加Authorization头
        if self.auth_client and self.auth_client.is_authenticated():
            try:
                auth_header = self.auth_client.get_auth_header()
                headers.update(auth_header)
            except:
                pass  # 未认证时忽略
        
        return headers
    
    def update_file(
        self, 
        file_id: int,
        file_path: str, 
        show_progress: bool = True,
        enable_compression: bool = True
    ) -> Dict:
        """
        更新文件内容（上传新版本）
        
        Args:
            file_id: 要更新的文件ID
            file_path: 本地新文件路径
            show_progress: 是否显示进度条
            enable_compression: 是否启用压缩（默认True）
            
        Returns:
            上传结果
        """
        if not os.path.exists(file_path):
            return {"success": False, "error": "文件不存在"}

        # Get the current version of the file for conflict detection
        file_info = self.get_file_info(file_id, quiet=True)
        if not file_info:
            print(f"✗ Cannot update file: File with ID {file_id} not found or no access.")
            return {"success": False, "error": "File not found or no access."}
        base_version = file_info.get('version')
        
        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        
        print(f"Updating file: {filename} (ID: {file_id}, base version: {base_version}) -> {file_size / 1024 / 1024:.2f} MB")
        
        url = f"{self.base_url}/api/files/update/{file_id}"
        params = {
            "base_version": base_version,
            "enable_compression": enable_compression
        }
        
        with open(file_path, 'rb') as f:
            if show_progress:
                progress_bar = tqdm(
                    total=file_size,
                    unit='B',
                    unit_scale=True,
                    desc=f"Updating {filename}"
                )
                
                original_read = f.read
                def read_with_progress(size=-1):
                    data = original_read(size)
                    progress_bar.update(len(data))
                    return data
                f.read = read_with_progress
            
            files = {'file': (filename, f)}
            headers = self._get_headers()
            
            try:
                response = self.session.post(url, files=files, params=params, headers=headers)
                
                if show_progress:
                    progress_bar.close()
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✓ {result['message']}")
                    return result
                else:
                    error_msg = response.json().get('detail', 'Unknown error')
                    print(f"✗ Update failed: {error_msg}")
                    return {"success": False, "error": error_msg}
                    
            except Exception as e:
                if show_progress:
                    progress_bar.close()
                print(f"✗ Update exception: {str(e)}")
                return {"success": False, "error": str(e)}

    def upload_file(
        self, 
        file_path: str, 
        remote_path: str = "/",
        show_progress: bool = True,
        enable_compression: bool = True,
        enable_deduplication: bool = True,
        enable_block_deduplication: bool = True,
        enable_resumable: bool = True,
        chunk_size: int = None
    ) -> Dict:
        """
        上传文件
        
        Args:
            file_path: 本地文件路径
            remote_path: 远程目录路径
            show_progress: 是否显示进度条
            enable_compression: 是否启用压缩（默认True）
            enable_deduplication: 是否启用去重（默认True）
            enable_block_deduplication: 是否启用块级去重（默认True）
            chunk_size: 块大小（字节），仅用于块级去重
            
        Returns:
            上传结果
        """
        if not os.path.exists(file_path):
            return {"success": False, "error": "文件不存在"}
        
        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        
        print(f"上传文件: {filename} ({file_size / 1024 / 1024:.2f} MB)")
        
        # 判断是否使用块级去重
        if enable_block_deduplication and BlockUploadClient.should_use_block_chunking(file_size, chunk_size):
            print("使用块级去重上传...")
            try:
                headers = self._get_headers()
                result = BlockUploadClient.upload_file_with_blocks(
                    session=self.session,
                    base_url=self.base_url,
                    file_path=file_path,
                    remote_path=remote_path,
                    headers=headers,
                    chunk_size=chunk_size,
                    enable_compression=enable_compression,
                    show_progress=show_progress,
                    enable_resumable=enable_resumable
                )
                return result
            except Exception as e:
                print("--------------------------------")
                
                # 继续执行常规上传
        
        # 如果启用去重，先检查文件是否已存在
        if enable_deduplication:
            print("计算文件哈希...")
            hash_value = DeduplicationClient.calculate_file_hash(file_path)
            
            print("检查文件是否已存在...")
            headers = self._get_headers()
            duplicate_info = DeduplicationClient.check_duplicate(
                self.session,
                self.base_url,
                hash_value,
                file_size,
                headers
            )
            
            if duplicate_info and duplicate_info.get('exists'):
                # 文件已存在，通过引用上传
                print(f"✓ 文件已存在（被引用{duplicate_info.get('reference_count')}次），跳过上传")
                
                # 获取文件类型
                import mimetypes
                content_type, _ = mimetypes.guess_type(filename)
                
                result = DeduplicationClient.upload_by_reference(
                    self.session,
                    self.base_url,
                    filename,
                    remote_path,
                    duplicate_info['chunk_id'],
                    file_size,
                    hash_value,
                    content_type,
                    headers
                )
                
                if result.get('success'):
                    api_result = result['result']
                    file_info = api_result.get('file_info', {})
                    version = file_info.get('version', 1)
                    
                    print(f"✓ {api_result.get('message')} (版本: {version})")
                    
                    if duplicate_info.get('is_compressed'):
                        print(f"  文件已压缩，压缩率: {duplicate_info.get('compression_ratio')}%")
                    
                    return api_result
                else:
                    print(f"✗ 通过去重上传失败: {result.get('error')}")
                    print("  尝试常规上传...")
                    # 继续执行常规上传
        
        # 常规上传
        url = f"{self.base_url}/api/files/upload"
        
        # 准备文件
        with open(file_path, 'rb') as f:
            # 使用tqdm包装文件对象显示进度
            if show_progress:
                progress_bar = tqdm(
                    total=file_size,
                    unit='B',
                    unit_scale=True,
                    desc=f"上传 {filename}"
                )
                
                # 包装读取方法
                original_read = f.read
                def read_with_progress(size=-1):
                    data = original_read(size)
                    progress_bar.update(len(data))
                    return data
                f.read = read_with_progress
            
            files = {'file': (filename, f)}
            params = {
                'path': remote_path,
                'enable_compression': enable_compression
            }
            headers = self._get_headers()
            
            try:
                response = self.session.post(url, files=files, params=params, headers=headers)
                
                if show_progress:
                    progress_bar.close()
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✓ 上传成功: {filename} (版本: {result.get('file_info', {}).get('version')})")
                    return result
                else:
                    error_msg = response.json().get('detail', '未知错误')
                    print(f"✗ 上传失败: {error_msg}")
                    return {"success": False, "error": error_msg}
                    
            except Exception as e:
                if show_progress:
                    progress_bar.close()
                print(f"✗ 上传异常: {str(e)}")
                return {"success": False, "error": str(e)}
    
    def download_file(
        self, 
        file_id: int, 
        output_path: Optional[str] = None,
        show_progress: bool = True
    ) -> Dict:
        """
        下载文件
        
        Args:
            file_id: 文件ID
            output_path: 输出路径（可选）
            show_progress: 是否显示进度条
            
        Returns:
            下载结果
        """
        url = f"{self.base_url}/api/files/download/{file_id}"
        
        try:
            # 流式下载
            headers = self._get_headers()
            response = self.session.get(url, stream=True, headers=headers)
            
            if response.status_code != 200:
                error_msg = response.json().get('detail', '未知错误')
                print(f"✗ 下载失败: {error_msg}")
                return {"success": False, "error": error_msg}
            
            # 获取文件名
            content_disposition = response.headers.get('content-disposition', '')
            filename = None
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"')
            else:
                filename = f"file_{file_id}"
            
            # 确定输出路径
            if output_path is None:
                os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
                output_path = os.path.join(config.DOWNLOAD_DIR, filename)
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            
            print(f"下载文件: {filename} ({total_size / 1024 / 1024:.2f} MB)")
            
            # 下载文件
            with open(output_path, 'wb') as f:
                if show_progress and total_size > 0:
                    progress_bar = tqdm(
                        total=total_size,
                        unit='B',
                        unit_scale=True,
                        desc=f"下载 {filename}"
                    )
                    
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            progress_bar.update(len(chunk))
                    
                    progress_bar.close()
                else:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            
            print(f"✓ 下载成功: {output_path}")
            return {"success": True, "path": output_path}
            
        except Exception as e:
            print(f"✗ 下载异常: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def list_files(self, path: str = "/") -> List[Dict]:
        """
        列出文件
        
        Args:
            path: 目录路径
            
        Returns:
            文件列表
        """
        url = f"{self.base_url}/api/files/list"
        params = {'path': path}
        headers = self._get_headers()
        
        try:
            response = self.session.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                files = result.get('files', [])
                print(f"\n目录: {path}")
                print(f"{'类型':<8} {'ID':<6} {'版本':<6} {'大小':<15} {'文件名'}")
                print("-" * 60)
                
                for file in files:
                    file_type = "📁 目录" if file['is_directory'] else "📄 文件"
                    size_str = "-" if file['is_directory'] else f"{file['size'] / 1024:.2f} KB"
                    version_str = f"v{file['version']}" if not file['is_directory'] else "-"
                    print(f"{file_type:<8} {file['id']:<6} {version_str:<6} {size_str:<15} {file['filename']}")
                
                print(f"\n总计: {len(files)} 项")
                return files
            else:
                error_msg = response.json().get('detail', '未知错误')
                print(f"✗ 列表获取失败: {error_msg}")
                return []
                
        except Exception as e:
            print(f"✗ 列表获取异常: {str(e)}")
            return []
    
    def delete_file(self, file_id: int) -> Dict:
        """
        删除文件
        
        Args:
            file_id: 文件ID
            
        Returns:
            删除结果
        """
        url = f"{self.base_url}/api/files/delete/{file_id}"
        headers = self._get_headers()
        
        try:
            response = self.session.delete(url, headers=headers)
            
            if response.status_code == 200:
                print(f"✓ 删除成功: 文件ID {file_id}")
                return response.json()
            else:
                error_msg = response.json().get('detail', '未知错误')
                print(f"✗ 删除失败: {error_msg}")
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            print(f"✗ 删除异常: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def create_directory(self, path: str) -> Dict:
        """
        创建目录
        
        Args:
            path: 目录路径
            
        Returns:
            创建结果
        """
        url = f"{self.base_url}/api/files/mkdir"
        params = {'path': path}
        headers = self._get_headers()
        
        try:
            response = self.session.post(url, params=params, headers=headers)
            
            if response.status_code == 200:
                print(f"✓ 创建目录成功: {path}")
                return response.json()
            else:
                error_msg = response.json().get('detail', '未知错误')
                print(f"✗ 创建目录失败: {error_msg}")
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            print(f"✗ 创建目录异常: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_file_info(self, file_id: int, quiet: bool = False) -> Optional[Dict]:
        """
        获取文件信息
        
        Args:
            file_id: 文件ID
            quiet: If True, suppresses console output.
            
        Returns:
            文件信息
        """
        url = f"{self.base_url}/api/files/info/{file_id}"
        headers = self._get_headers()
        
        try:
            response = self.session.get(url, headers=headers)
            
            if response.status_code == 200:
                info = response.json()
                if not quiet:
                    print(f"\n文件信息:")
                    print(f"  ID: {info['id']}")
                    print(f"  文件名: {info['filename']}")
                    print(f"  路径: {info['path']}")
                    print(f"  大小: {info['size'] / 1024 / 1024:.2f} MB")
                    print(f"  版本: {info['version']}")
                    print(f"  类型: {info.get('content_type', 'unknown')}")
                    print(f"  哈希: {info.get('hash_value', 'N/A')}")
                    print(f"  创建时间: {info['created_at']}")
                    print(f"  更新时间: {info['updated_at']}")
                return info
            else:
                if not quiet:
                    error_msg = response.json().get('detail', '未知错误')
                    print(f"✗ 获取信息失败: {error_msg}")
                return None
                
        except Exception as e:
            if not quiet:
                print(f"✗ 获取信息异常: {str(e)}")
            return None

    def get_file_history(self, file_id: int) -> Optional[List[Dict]]:
        """
        获取文件历史版本
        """
        url = f"{self.base_url}/api/files/history/{file_id}"
        headers = self._get_headers()
        
        try:
            response = self.session.get(url, headers=headers)
            
            if response.status_code == 200:
                history = response.json()
                print(f"\n文件历史: ID={file_id}")
                if not history:
                    print("  无历史版本")
                    return history
                
                print(f"  {'版本':<8} {'大小':<15} {'哈希':<20} {'创建时间'}")
                print("  " + "-" * 60)
                for h in history:
                    size_str = f"{h['size'] / 1024:.2f} KB"
                    hash_str = h.get('hash_value', 'N/A')[:16] + "..."
                    print(f"  {h['version']:<8} {size_str:<15} {hash_str:<20} {h['created_at']}")
                return history
            else:
                error_msg = response.json().get('detail', '未知错误')
                print(f"✗ 获取历史失败: {error_msg}")
                return None
        except Exception as e:
            print(f"✗ 获取历史异常: {str(e)}")
            return None

    def revert_file(self, file_id: int, version: int) -> Optional[Dict]:
        """
        回滚文件到指定版本
        """
        url = f"{self.base_url}/api/files/revert/{file_id}"
        params = {"version": version}
        headers = self._get_headers()
        
        try:
            response = self.session.post(url, params=params, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ {result['message']}")
                print(f"  新版本号: {result['file_info']['version']}")
                return result
            else:
                error_msg = response.json().get('detail', '未知错误')
                print(f"✗ 回滚失败: {error_msg}")
                return None
        except Exception as e:
            print(f"✗ 回滚异常: {str(e)}")
            return None

    # ==================== 共享功能 ====================
    
    def create_share(
        self, 
        file_id: int, 
        shared_with_username: str, 
        permission: str = "read",
        expires_at: Optional[str] = None
    ) -> Optional[Dict]:
        """
        创建文件共享
        
        Args:
            file_id: 文件ID
            shared_with_username: 要分享给的用户名
            permission: 权限 (read/write)
            expires_at: 过期时间 (ISO格式，可选)
            
        Returns:
            共享信息
        """
        url = f"{self.base_url}/api/share/create"
        headers = self._get_headers()
        
        data = {
            "file_id": file_id,
            "shared_with_username": shared_with_username,
            "permission": permission
        }
        
        if expires_at:
            data["expires_at"] = expires_at
        
        try:
            response = self.session.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ {result['message']}")
                share_info = result.get('share_info', {})
                print(f"  共享ID: {share_info.get('id')}")
                print(f"  文件: {share_info.get('filename')}")
                print(f"  分享给: {share_info.get('shared_with_username')}")
                print(f"  权限: {share_info.get('permission')}")
                if share_info.get('expires_at'):
                    print(f"  过期时间: {share_info.get('expires_at')}")
                return result
            else:
                error_msg = response.json().get('detail', '未知错误')
                print(f"✗ 创建共享失败: {error_msg}")
                return None
        except Exception as e:
            print(f"✗ 创建共享异常: {str(e)}")
            return None
    
    def list_my_shares(self) -> Optional[List[Dict]]:
        """
        列出我创建的所有共享
        
        Returns:
            共享列表
        """
        url = f"{self.base_url}/api/share/my-shares"
        headers = self._get_headers()
        
        try:
            response = self.session.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                shares = result.get('shares', [])
                total = result.get('total', 0)
                
                print(f"\n我的共享 (共 {total} 项):")
                if total == 0:
                    print("  暂无共享")
                    return []
                
                print(f"\n  {'ID':<6} {'文件名':<25} {'分享给':<15} {'权限':<8} {'状态':<8} {'过期时间'}")
                print("  " + "-" * 90)
                
                for share in shares:
                    share_id = share.get('id', 'N/A')
                    filename = share.get('filename', 'N/A')[:23]
                    shared_with = share.get('shared_with_username', 'N/A')[:13]
                    permission = share.get('permission', 'N/A')
                    status = "有效" if share.get('is_valid') else ("过期" if share.get('is_expired') else "禁用")
                    expires = share.get('expires_at', '永久')[:19] if share.get('expires_at') else '永久'
                    
                    print(f"  {share_id:<6} {filename:<25} {shared_with:<15} {permission:<8} {status:<8} {expires}")
                
                return shares
            else:
                error_msg = response.json().get('detail', '未知错误')
                print(f"✗ 获取共享列表失败: {error_msg}")
                return None
        except Exception as e:
            print(f"✗ 获取共享列表异常: {str(e)}")
            return None
    
    def list_shared_with_me(self) -> Optional[List[Dict]]:
        """
        列出分享给我的所有文件
        
        Returns:
            共享列表
        """
        url = f"{self.base_url}/api/share/shared-with-me"
        headers = self._get_headers()
        
        try:
            response = self.session.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                shares = result.get('shares', [])
                total = result.get('total', 0)
                
                print(f"\n分享给我的文件 (共 {total} 项):")
                if total == 0:
                    print("  暂无共享文件")
                    return []
                
                print(f"\n  {'ID':<6} {'文件名':<25} {'所有者':<15} {'权限':<8} {'文件ID':<8} {'过期时间'}")
                print("  " + "-" * 90)
                
                for share in shares:
                    share_id = share.get('id', 'N/A')
                    filename = share.get('filename', 'N/A')[:23]
                    owner = share.get('owner_username', 'N/A')[:13]
                    permission = share.get('permission', 'N/A')
                    file_id = share.get('file_id', 'N/A')
                    expires = share.get('expires_at', '永久')[:19] if share.get('expires_at') else '永久'
                    
                    print(f"  {share_id:<6} {filename:<25} {owner:<15} {permission:<8} {file_id:<8} {expires}")
                
                return shares
            else:
                error_msg = response.json().get('detail', '未知错误')
                print(f"✗ 获取共享列表失败: {error_msg}")
                return None
        except Exception as e:
            print(f"✗ 获取共享列表异常: {str(e)}")
            return None
    
    def update_share(
        self, 
        share_id: int, 
        permission: Optional[str] = None,
        is_active: Optional[bool] = None,
        expires_at: Optional[str] = None
    ) -> Optional[Dict]:
        """
        更新共享设置
        
        Args:
            share_id: 共享ID
            permission: 新权限 (read/write)
            is_active: 是否启用
            expires_at: 过期时间
            
        Returns:
            更新结果
        """
        url = f"{self.base_url}/api/share/update/{share_id}"
        headers = self._get_headers()
        
        data = {}
        if permission is not None:
            data["permission"] = permission
        if is_active is not None:
            data["is_active"] = is_active
        if expires_at is not None:
            data["expires_at"] = expires_at
        
        try:
            response = self.session.put(url, json=data, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ {result['message']}")
                return result
            else:
                error_msg = response.json().get('detail', '未知错误')
                print(f"✗ 更新共享失败: {error_msg}")
                return None
        except Exception as e:
            print(f"✗ 更新共享异常: {str(e)}")
            return None
    
    def delete_share(self, share_id: int) -> Optional[Dict]:
        """
        删除共享
        
        Args:
            share_id: 共享ID
            
        Returns:
            删除结果
        """
        url = f"{self.base_url}/api/share/delete/{share_id}"
        headers = self._get_headers()
        
        try:
            response = self.session.delete(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ {result['message']}")
                return result
            else:
                error_msg = response.json().get('detail', '未知错误')
                print(f"✗ 删除共享失败: {error_msg}")
                return None
        except Exception as e:
            print(f"✗ 删除共享异常: {str(e)}")
            return None
    
    def get_share_info(self, share_id: int) -> Optional[Dict]:
        """
        获取共享详情
        
        Args:
            share_id: 共享ID
            
        Returns:
            共享信息
        """
        url = f"{self.base_url}/api/share/info/{share_id}"
        headers = self._get_headers()
        
        try:
            response = self.session.get(url, headers=headers)
            
            if response.status_code == 200:
                share = response.json()
                print(f"\n共享详情:")
                print(f"  共享ID: {share.get('id')}")
                print(f"  文件: {share.get('filename')} (ID: {share.get('file_id')})")
                print(f"  路径: {share.get('file_path')}")
                print(f"  所有者: {share.get('owner_username')}")
                print(f"  分享给: {share.get('shared_with_username')}")
                print(f"  权限: {share.get('permission')}")
                print(f"  状态: {'有效' if share.get('is_valid') else ('过期' if share.get('is_expired') else '禁用')}")
                print(f"  创建时间: {share.get('created_at')}")
                if share.get('expires_at'):
                    print(f"  过期时间: {share.get('expires_at')}")
                return share
            else:
                error_msg = response.json().get('detail', '未知错误')
                print(f"✗ 获取共享信息失败: {error_msg}")
                return None
        except Exception as e:
            print(f"✗ 获取共享信息异常: {str(e)}")
            return None


def main():
    """主函数 - 交互式命令行"""
    import click
    
    @click.group()
    def cli():
        """云盘客户端命令行工具"""
        pass
    
    @cli.command()
    @click.option('--username', prompt=True, help='用户名')
    @click.option('--email', prompt=True, help='邮箱')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='密码')
    def register(username, email, password):
        """注册新用户"""
        auth_client = AuthClient(config.API_BASE_URL)
        result = auth_client.register(username, email, password)
        
        if result.get('success'):
            print(f"\n✓ 注册成功！")
            print(f"  用户名: {result.get('username')}")
            print(f"  用户ID: {result.get('user_id')}")
            print(f"\n现在可以使用客户端上传下载文件了")
        else:
            print(f"\n✗ 注册失败: {result.get('error')}")
    
    @cli.command()
    @click.option('--username', prompt=True, help='用户名')
    @click.option('--password', prompt=True, hide_input=True, help='密码')
    def login(username, password):
        """用户登录"""
        auth_client = AuthClient(config.API_BASE_URL)
        result = auth_client.login(username, password)
        
        if result.get('success'):
            print(f"\n✓ 登录成功！")
            print(f"  用户名: {result.get('username')}")
            print(f"  用户ID: {result.get('user_id')}")
            print(f"\nToken已保存，后续操作将自动认证")
        else:
            print(f"\n✗ 登录失败: {result.get('error')}")
    
    @cli.command()
    def logout():
        """退出登录"""
        auth_client = AuthClient(config.API_BASE_URL)
        auth_client.logout()
        print("\n✓ 已退出登录")
    
    @cli.command()
    def whoami():
        """查看当前登录用户"""
        auth_client = AuthClient(config.API_BASE_URL)
        
        if not auth_client.is_authenticated():
            print("\n未登录")
            print("使用 'python client.py login' 登录")
            return
        
        result = auth_client.get_user_info()
        
        if result.get('success'):
            print(f"\n当前用户:")
            print(f"  用户名: {result.get('username')}")
            print(f"  邮箱: {result.get('email')}")
            print(f"  用户ID: {result.get('id')}")
            print(f"  注册时间: {result.get('created_at')}")
        else:
            print(f"\n获取用户信息失败: {result.get('error')}")
    
    @cli.command()
    @click.argument('file_path')
    @click.option('--path', default='/', help='远程目录路径')
    @click.option('--no-compression', is_flag=True, help='禁用压缩')
    @click.option('--no-dedup', is_flag=True, help='禁用文件级去重')
    @click.option('--no-block-dedup', is_flag=True, help='禁用块级去重')
    @click.option('--chunk-size', type=int, help='块大小（MB），用于块级去重')
    @click.option('--no-resume', is_flag=True, help='禁用断点续传')
    def upload(file_path, path, no_compression, no_dedup, no_block_dedup, chunk_size, no_resume):
        """上传新文件
        
        示例：
        
        \b
        # 基本上传（自动选择最优策略）
        python client.py upload test.bin
        
        \b
        # 上传到指定目录
        python client.py upload test.bin --path /documents
        
        \b
        # 禁用压缩
        python client.py upload test.bin --no-compression
        
        \b
        # 强制使用块级去重，指定2MB块大小
        python client.py upload large_file.bin --chunk-size 2
        
        \b
        # 禁用所有去重功能
        python client.py upload test.bin --no-dedup --no-block-dedup
        """
        client = CloudDriveClient()
        
        # 转换块大小为字节
        chunk_size_bytes = None
        if chunk_size:
            chunk_size_bytes = chunk_size * 1024 * 1024
        
        client.upload_file(
            file_path, 
            path,
            enable_compression=not no_compression,
            enable_deduplication=not no_dedup,
            enable_block_deduplication=not no_block_dedup,
            chunk_size=chunk_size_bytes,
            enable_resumable=not no_resume
        )

    @cli.command()
    @click.argument('file_id', type=int)
    @click.argument('file_path', type=click.Path(exists=True))
    def update(file_id, file_path):
        """更新文件内容（上传新版本）"""
        client = CloudDriveClient()
        client.update_file(file_id, file_path)
    
    @cli.command()
    @click.argument('file_id', type=int)
    @click.option('--output', default=None, help='输出路径')
    def download(file_id, output):
        """下载文件"""
        client = CloudDriveClient()
        client.download_file(file_id, output)
    
    @cli.command()
    @click.option('--path', default='/', help='目录路径')
    def list(path):
        """列出文件"""
        client = CloudDriveClient()
        client.list_files(path)
    
    @cli.command()
    @click.argument('file_id', type=int)
    def delete(file_id):
        """删除文件"""
        client = CloudDriveClient()
        client.delete_file(file_id)
    
    @cli.command()
    @click.argument('path')
    def mkdir(path):
        """创建目录"""
        client = CloudDriveClient()
        client.create_directory(path)
    
    @cli.command()
    @click.argument('file_id', type=int)
    def info(file_id):
        """获取文件信息"""
        client = CloudDriveClient()
        client.get_file_info(file_id)

    @cli.command()
    @click.argument('file_id', type=int)
    def history(file_id):
        """查看文件历史版本"""
        client = CloudDriveClient()
        client.get_file_history(file_id)

    @cli.command()
    @click.argument('file_id', type=int)
    @click.argument('version', type=int)
    def revert(file_id, version):
        """回滚文件到指定版本"""
        client = CloudDriveClient()
        client.revert_file(file_id, version)
    
    # ==================== 共享命令 ====================
    
    @cli.command()
    @click.argument('file_id', type=int)
    @click.argument('username')
    @click.option('--permission', type=click.Choice(['read', 'write']), default='read', help='权限 (read/write)')
    @click.option('--expires', help='过期时间 (ISO格式，如: 2024-12-31T23:59:59)')
    def share(file_id, username, permission, expires):
        """创建文件共享"""
        client = CloudDriveClient()
        client.create_share(file_id, username, permission, expires)
    
    @cli.command()
    def my_shares():
        """列出我创建的所有共享"""
        client = CloudDriveClient()
        client.list_my_shares()
    
    @cli.command()
    def shared_with_me():
        """列出分享给我的所有文件"""
        client = CloudDriveClient()
        client.list_shared_with_me()
    
    @cli.command()
    @click.argument('share_id', type=int)
    def share_info(share_id):
        """查看共享详情"""
        client = CloudDriveClient()
        client.get_share_info(share_id)
    
    @cli.command()
    @click.argument('share_id', type=int)
    @click.option('--permission', type=click.Choice(['read', 'write']), help='新权限')
    @click.option('--active/--inactive', default=None, help='启用/禁用共享')
    @click.option('--expires', help='过期时间 (ISO格式)')
    def update_share(share_id, permission, active, expires):
        """更新共享设置"""
        client = CloudDriveClient()
        client.update_share(share_id, permission, active, expires)
    
    @cli.command()
    @click.argument('share_id', type=int)
    @click.confirmation_option(prompt='确定要删除此共享吗?')
    def unshare(share_id):
        """删除共享"""
        client = CloudDriveClient()
        client.delete_share(share_id)
    
    # ==================== 块级去重命令 ====================
    
    @cli.command()
    def block_stats():
        """查看块级去重统计信息"""
        client = CloudDriveClient()
        headers = client._get_headers()
        
        try:
            response = client.session.get(
                f"{client.base_url}/api/block-upload/stats",
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    stats = result['stats']
                    
                    print("\n" + "=" * 60)
                    print("块级去重统计信息")
                    print("=" * 60)
                    
                    print(f"\n数据块统计:")
                    print(f"  总数据块数:     {stats['total_blocks']}")
                    print(f"  总引用次数:     {stats['total_references']}")
                    print(f"  压缩块数:       {stats['compressed_blocks']}")
                    
                    print(f"\n存储空间:")
                    print(f"  实际存储:       {stats['total_size_mb']:.2f} MB")
                    print(f"  节省空间:       {stats['saved_space_mb']:.2f} MB")
                    print(f"  去重率:         {stats['deduplication_ratio']}%")
                    
                    if stats['compressed_blocks'] > 0:
                        print(f"  压缩后大小:     {stats['total_compressed_size_mb']:.2f} MB")
                    
                    print("\n" + "=" * 60)
                else:
                    print(f"✗ 获取统计失败")
            else:
                error_msg = response.json().get('detail', '未知错误')
                print(f"✗ API调用失败: {error_msg}")
        except Exception as e:
            print(f"✗ 获取统计异常: {str(e)}")
    
    @cli.command()
    @click.argument('file_path')
    @click.option('--path', default='/', help='远程目录路径')
    @click.option('--chunk-size', type=int, default=4, help='块大小（MB），默认4MB')
    @click.option('--no-compression', is_flag=True, help='禁用压缩')
    def block_upload(file_path, path, chunk_size, no_compression):
        """强制使用块级去重上传文件
        
        示例：
        
        \b
        # 使用默认4MB块大小上传
        python client.py block-upload large_file.bin
        
        \b
        # 使用2MB块大小上传
        python client.py block-upload large_file.bin --chunk-size 2
        
        \b
        # 禁用压缩
        python client.py block-upload large_file.bin --no-compression
        """
        from block_upload_client import BlockUploadClient
        
        if not os.path.exists(file_path):
            print(f"✗ 文件不存在: {file_path}")
            return
        
        client = CloudDriveClient()
        headers = client._get_headers()
        
        chunk_size_bytes = chunk_size * 1024 * 1024
        
        try:
            result = BlockUploadClient.upload_file_with_blocks(
                session=client.session,
                base_url=client.base_url,
                file_path=file_path,
                remote_path=path,
                headers=headers,
                chunk_size=chunk_size_bytes,
                enable_compression=not no_compression,
                show_progress=True
            )
            
            if result.get('success'):
                print(f"\n✓ 上传成功!")
                print(f"  文件ID: {result.get('file_id')}")
                print(f"  版本: {result.get('version')}")
            else:
                print(f"\n✗ 上传失败: {result.get('error')}")
        except Exception as e:
            print(f"\n✗ 上传异常: {str(e)}")
    
    cli()


if __name__ == "__main__":
    main()
