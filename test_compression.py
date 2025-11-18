"""
压缩功能测试脚本
用于测试文件上传下载的压缩和解压功能
"""
import os
import sys
import hashlib
import random
import string

# 添加client目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client'))

from client.client import CloudDriveClient
from client.src.auth_client import AuthClient
from client.config import config


def generate_test_file(filename: str, size_mb: int, compressible: bool = True):
    """
    生成测试文件
    
    Args:
        filename: 文件名
        size_mb: 文件大小（MB）
        compressible: 是否生成可压缩的文件（文本）还是不可压缩的（随机二进制）
    """
    print(f"\n生成测试文件: {filename} ({size_mb} MB, {'可压缩' if compressible else '不可压缩'})")
    
    size_bytes = size_mb * 1024 * 1024
    
    with open(filename, 'wb') as f:
        if compressible:
            # 生成可压缩的文本数据（重复模式）
            pattern = "This is a test file for compression. " * 100
            pattern_bytes = pattern.encode('utf-8')
            pattern_size = len(pattern_bytes)
            
            written = 0
            while written < size_bytes:
                chunk_size = min(pattern_size, size_bytes - written)
                f.write(pattern_bytes[:chunk_size])
                written += chunk_size
        else:
            # 生成不可压缩的随机数据
            chunk_size = 1024 * 1024  # 1MB chunks
            written = 0
            while written < size_bytes:
                chunk = os.urandom(min(chunk_size, size_bytes - written))
                f.write(chunk)
                written += len(chunk)
    
    print(f"✓ 文件已生成: {filename}")
    return filename


def calculate_file_hash(filename: str) -> str:
    """计算文件的SHA-256哈希值"""
    sha256_hash = hashlib.sha256()
    with open(filename, 'rb') as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def test_compression_feature():
    """测试压缩功能"""
    print("=" * 80)
    print("压缩功能测试")
    print("=" * 80)
    
    # 初始化客户端
    auth_client = AuthClient(config.API_BASE_URL)
    client = CloudDriveClient(auth_client=auth_client)
    
    # 检查是否已登录
    if not auth_client.is_authenticated():
        print("\n请先登录:")
        print("  python client/client.py login")
        return
    
    user_info = auth_client.get_user_info()
    print(f"\n当前用户: {user_info.get('username')}")
    
    # 测试文件列表
    test_files = []
    
    try:
        # 1. 测试小文件（不会被压缩）
        print("\n" + "=" * 80)
        print("测试 1: 小文件（< 1KB，不会被压缩）")
        print("=" * 80)
        
        small_file = "test_small.txt"
        with open(small_file, 'w') as f:
            f.write("Small file content")
        test_files.append(small_file)
        
        print(f"文件大小: {os.path.getsize(small_file)} 字节")
        hash_before = calculate_file_hash(small_file)
        print(f"上传前哈希: {hash_before}")
        
        result = client.upload_file(small_file, "/")
        if result.get('success'):
            file_info = result.get('file_info', {})
            file_id = file_info.get('id')
            is_compressed = file_info.get('is_compressed', False)
            
            print(f"文件ID: {file_id}")
            print(f"是否压缩: {is_compressed}")
            print(f"预期: 不压缩（文件太小）")
            
            if not is_compressed:
                print("✓ 测试通过：小文件未被压缩")
            else:
                print("✗ 测试失败：小文件不应该被压缩")
            
            # 下载并验证
            download_result = client.download_file(file_id)
            if download_result.get('success'):
                downloaded_path = download_result.get('path')
                hash_after = calculate_file_hash(downloaded_path)
                print(f"下载后哈希: {hash_after}")
                
                if hash_before == hash_after:
                    print("✓ 哈希验证通过：文件完整")
                else:
                    print("✗ 哈希验证失败：文件损坏")
        
        # 2. 测试可压缩的文本文件
        print("\n" + "=" * 80)
        print("测试 2: 可压缩文本文件（10MB）")
        print("=" * 80)
        
        text_file = generate_test_file("test_compressible_10mb.txt", 10, compressible=True)
        test_files.append(text_file)
        
        original_size = os.path.getsize(text_file)
        print(f"原始大小: {original_size / 1024 / 1024:.2f} MB")
        hash_before = calculate_file_hash(text_file)
        print(f"上传前哈希: {hash_before}")
        
        result = client.upload_file(text_file, "/")
        if result.get('success'):
            file_info = result.get('file_info', {})
            file_id = file_info.get('id')
            is_compressed = file_info.get('is_compressed', False)
            compressed_size = file_info.get('compressed_size')
            compression_ratio = file_info.get('compression_ratio')
            
            print(f"文件ID: {file_id}")
            print(f"是否压缩: {is_compressed}")
            
            if is_compressed:
                print(f"压缩后大小: {compressed_size / 1024 / 1024:.2f} MB")
                print(f"压缩率: {compression_ratio}%")
                print(f"节省空间: {(original_size - compressed_size) / 1024 / 1024:.2f} MB")
                print("✓ 测试通过：文件已压缩")
            else:
                print("✗ 测试失败：可压缩文件应该被压缩")
            
            # 下载并验证
            print("\n下载文件...")
            download_result = client.download_file(file_id)
            if download_result.get('success'):
                downloaded_path = download_result.get('path')
                hash_after = calculate_file_hash(downloaded_path)
                print(f"下载后哈希: {hash_after}")
                
                if hash_before == hash_after:
                    print("✓ 哈希验证通过：文件完整（自动解压成功）")
                else:
                    print("✗ 哈希验证失败：文件损坏")
        
        # 3. 测试不可压缩的二进制文件
        print("\n" + "=" * 80)
        print("测试 3: 不可压缩二进制文件（5MB随机数据）")
        print("=" * 80)
        
        binary_file = generate_test_file("test_random_5mb.bin", 5, compressible=False)
        test_files.append(binary_file)
        
        original_size = os.path.getsize(binary_file)
        print(f"原始大小: {original_size / 1024 / 1024:.2f} MB")
        hash_before = calculate_file_hash(binary_file)
        print(f"上传前哈希: {hash_before}")
        
        result = client.upload_file(binary_file, "/")
        if result.get('success'):
            file_info = result.get('file_info', {})
            file_id = file_info.get('id')
            is_compressed = file_info.get('is_compressed', False)
            
            print(f"文件ID: {file_id}")
            print(f"是否压缩: {is_compressed}")
            
            if is_compressed:
                compressed_size = file_info.get('compressed_size')
                compression_ratio = file_info.get('compression_ratio')
                print(f"压缩后大小: {compressed_size / 1024 / 1024:.2f} MB")
                print(f"压缩率: {compression_ratio}%")
                
                if compression_ratio < 5:
                    print("✓ 随机数据压缩率很低（符合预期）")
                else:
                    print("✗ 随机数据不应该有高压缩率")
            
            # 下载并验证
            print("\n下载文件...")
            download_result = client.download_file(file_id)
            if download_result.get('success'):
                downloaded_path = download_result.get('path')
                hash_after = calculate_file_hash(downloaded_path)
                print(f"下载后哈希: {hash_after}")
                
                if hash_before == hash_after:
                    print("✓ 哈希验证通过：文件完整")
                else:
                    print("✗ 哈希验证失败：文件损坏")
        
        # 4. 测试大文件（结合多线程上传和压缩）
        print("\n" + "=" * 80)
        print("测试 4: 大文件（50MB，测试多线程上传+压缩）")
        print("=" * 80)
        
        large_file = generate_test_file("test_large_50mb.txt", 50, compressible=True)
        test_files.append(large_file)
        
        original_size = os.path.getsize(large_file)
        print(f"原始大小: {original_size / 1024 / 1024:.2f} MB")
        hash_before = calculate_file_hash(large_file)
        print(f"上传前哈希: {hash_before}")
        
        result = client.upload_file(large_file, "/")
        if result.get('success'):
            file_info = result.get('file_info', {})
            file_id = file_info.get('id')
            is_compressed = file_info.get('is_compressed', False)
            
            print(f"文件ID: {file_id}")
            print(f"是否压缩: {is_compressed}")
            
            if is_compressed:
                compressed_size = file_info.get('compressed_size')
                compression_ratio = file_info.get('compression_ratio')
                print(f"压缩后大小: {compressed_size / 1024 / 1024:.2f} MB")
                print(f"压缩率: {compression_ratio}%")
                print(f"节省空间: {(original_size - compressed_size) / 1024 / 1024:.2f} MB")
                print("✓ 大文件压缩成功")
            
            # 下载并验证
            print("\n下载文件...")
            download_result = client.download_file(file_id)
            if download_result.get('success'):
                downloaded_path = download_result.get('path')
                hash_after = calculate_file_hash(downloaded_path)
                print(f"下载后哈希: {hash_after}")
                
                if hash_before == hash_after:
                    print("✓ 哈希验证通过：大文件完整（多线程+压缩成功）")
                else:
                    print("✗ 哈希验证失败：文件损坏")
        
        # 5. 测试已压缩格式（如ZIP、JPG）
        print("\n" + "=" * 80)
        print("测试 5: 已压缩格式（模拟JPG文件）")
        print("=" * 80)
        
        # 创建一个假的JPG文件（实际是随机数据）
        jpg_file = "test_image.jpg"
        with open(jpg_file, 'wb') as f:
            f.write(os.urandom(2 * 1024 * 1024))  # 2MB
        test_files.append(jpg_file)
        
        print(f"文件大小: {os.path.getsize(jpg_file) / 1024 / 1024:.2f} MB")
        hash_before = calculate_file_hash(jpg_file)
        
        result = client.upload_file(jpg_file, "/")
        if result.get('success'):
            file_info = result.get('file_info', {})
            is_compressed = file_info.get('is_compressed', False)
            
            print(f"是否压缩: {is_compressed}")
            print(f"预期: 不压缩（已经是压缩格式）")
            
            if not is_compressed:
                print("✓ 测试通过：JPG文件未被再次压缩")
            else:
                print("⚠ JPG文件被压缩了（可能MIME类型未正确识别）")
        
        print("\n" + "=" * 80)
        print("测试完成！")
        print("=" * 80)
        
        print("\n查看所有上传的文件:")
        client.list_files("/")
        
    finally:
        # 清理测试文件
        print("\n清理测试文件...")
        for test_file in test_files:
            if os.path.exists(test_file):
                os.remove(test_file)
                print(f"✓ 已删除: {test_file}")


if __name__ == "__main__":
    test_compression_feature()

