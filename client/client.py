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
    
    def upload_file(
        self, 
        file_path: str, 
        remote_path: str = "/",
        show_progress: bool = True
    ) -> Dict:
        """
        上传文件
        
        Args:
            file_path: 本地文件路径
            remote_path: 远程目录路径
            show_progress: 是否显示进度条
            
        Returns:
            上传结果
        """
        if not os.path.exists(file_path):
            return {"success": False, "error": "文件不存在"}
        
        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        
        print(f"上传文件: {filename} ({file_size / 1024 / 1024:.2f} MB)")
        
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
            params = {'path': remote_path}
            headers = self._get_headers()
            
            try:
                response = self.session.post(url, files=files, params=params, headers=headers)
                
                if show_progress:
                    progress_bar.close()
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✓ 上传成功: {filename}")
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
                print(f"{'类型':<8} {'ID':<6} {'大小':<15} {'文件名'}")
                print("-" * 60)
                
                for file in files:
                    file_type = "📁 目录" if file['is_directory'] else "📄 文件"
                    size_str = "-" if file['is_directory'] else f"{file['size'] / 1024:.2f} KB"
                    print(f"{file_type:<8} {file['id']:<6} {size_str:<15} {file['filename']}")
                
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
    
    def get_file_info(self, file_id: int) -> Optional[Dict]:
        """
        获取文件信息
        
        Args:
            file_id: 文件ID
            
        Returns:
            文件信息
        """
        url = f"{self.base_url}/api/files/info/{file_id}"
        headers = self._get_headers()
        
        try:
            response = self.session.get(url, headers=headers)
            
            if response.status_code == 200:
                info = response.json()
                print(f"\n文件信息:")
                print(f"  ID: {info['id']}")
                print(f"  文件名: {info['filename']}")
                print(f"  路径: {info['path']}")
                print(f"  大小: {info['size'] / 1024 / 1024:.2f} MB")
                print(f"  类型: {info.get('content_type', 'unknown')}")
                print(f"  哈希: {info.get('hash_value', 'N/A')}")
                print(f"  创建时间: {info['created_at']}")
                return info
            else:
                error_msg = response.json().get('detail', '未知错误')
                print(f"✗ 获取信息失败: {error_msg}")
                return None
                
        except Exception as e:
            print(f"✗ 获取信息异常: {str(e)}")
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
    def upload(file_path, path):
        """上传文件"""
        client = CloudDriveClient()
        client.upload_file(file_path, path)
    
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
    
    cli()


if __name__ == "__main__":
    main()

