"""
块级去重功能测试脚本

测试场景：
1. 基本块级去重功能
2. 大文件块级上传
3. 部分重复内容的文件
4. 块级去重与文件级去重的对比
5. 块级去重文件的下载和验证
"""
import os
import sys
import hashlib
import time

# 添加client目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client', 'src'))

from client import CloudDriveClient
from auth_client import AuthClient


def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def calculate_file_hash(file_path):
    """计算文件哈希"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while True:
            data = f.read(8192)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()


def create_test_file(filename, size_mb, pattern=None):
    """
    创建测试文件
    
    Args:
        filename: 文件名
        size_mb: 文件大小（MB）
        pattern: 数据模式（None=随机，'repeat'=重复，'mixed'=混合）
    """
    size_bytes = size_mb * 1024 * 1024
    
    with open(filename, 'wb') as f:
        if pattern == 'repeat':
            # 重复模式：使用相同的1MB数据重复写入
            chunk = b'A' * (1024 * 1024)
            for _ in range(size_mb):
                f.write(chunk)
        elif pattern == 'mixed':
            # 混合模式：50%重复，50%不同
            chunk_a = b'A' * (1024 * 1024)
            chunk_b = b'B' * (1024 * 1024)
            for i in range(size_mb):
                if i % 2 == 0:
                    f.write(chunk_a)
                else:
                    f.write(chunk_b)
        else:
            # 随机模式
            import random
            for _ in range(size_mb):
                chunk = bytes([random.randint(0, 255) for _ in range(1024 * 1024)])
                f.write(chunk)
    
    print(f"✓ 生成测试文件: {filename} ({size_mb} MB, pattern={pattern})")


def test_basic_block_deduplication(client):
    """测试1: 基本块级去重功能"""
    print_section("测试 1: 基本块级去重功能")
    
    # 创建一个10MB的文件（使用重复模式，应该有很高的去重率）
    test_file = "test_block_dedup_basic.bin"
    create_test_file(test_file, 10, pattern='repeat')
    
    try:
        # 上传文件（启用块级去重）
        print("\n第一次上传（应该上传所有块）:")
        result1 = client.upload_file(
            test_file,
            enable_block_deduplication=True,
            chunk_size=2 * 1024 * 1024  # 2MB块
        )
        
        if result1.get('success'):
            print(f"✓ 第一次上传成功")
            if result1.get('deduplication_stats'):
                stats = result1['deduplication_stats']
                print(f"  - 总块数: {stats['total_blocks']}")
                print(f"  - 唯一块数: {stats['unique_blocks']}")
                print(f"  - 去重率: {stats['deduplication_ratio']}%")
        else:
            print(f"✗ 第一次上传失败: {result1.get('error')}")
            return False
        
        # 创建另一个相同内容的文件
        test_file2 = "test_block_dedup_basic2.bin"
        create_test_file(test_file2, 10, pattern='repeat')
        
        print("\n第二次上传相同内容的文件（应该完全去重）:")
        result2 = client.upload_file(
            test_file2,
            enable_block_deduplication=True,
            chunk_size=2 * 1024 * 1024
        )
        
        if result2.get('success'):
            print(f"✓ 第二次上传成功")
            if result2.get('deduplication_stats'):
                stats = result2['deduplication_stats']
                print(f"  - 总块数: {stats['total_blocks']}")
                print(f"  - 唯一块数: {stats['unique_blocks']}")
                print(f"  - 去重率: {stats['deduplication_ratio']}%")
        else:
            print(f"✗ 第二次上传失败: {result2.get('error')}")
            return False
        
        print("\n✅ 测试通过: 基本块级去重功能")
        return True
    
    finally:
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)
        if os.path.exists(test_file2):
            os.remove(test_file2)


def test_large_file_block_upload(client):
    """测试2: 大文件块级上传"""
    print_section("测试 2: 大文件块级上传")
    
    # 创建一个20MB的文件
    test_file = "test_block_dedup_large.bin"
    create_test_file(test_file, 20, pattern='mixed')
    
    try:
        print("\n上传大文件（使用块级去重）:")
        start_time = time.time()
        
        result = client.upload_file(
            test_file,
            enable_block_deduplication=True,
            chunk_size=4 * 1024 * 1024  # 4MB块
        )
        
        elapsed_time = time.time() - start_time
        
        if result.get('success'):
            print(f"✓ 上传成功，耗时: {elapsed_time:.2f}秒")
            if result.get('deduplication_stats'):
                stats = result['deduplication_stats']
                print(f"  - 总块数: {stats['total_blocks']}")
                print(f"  - 唯一块数: {stats['unique_blocks']}")
                print(f"  - 去重率: {stats['deduplication_ratio']}%")
            
            file_id = result.get('file_id')
            
            # 下载文件验证
            print("\n下载文件验证完整性:")
            download_path = "downloads/test_block_dedup_large_downloaded.bin"
            os.makedirs("downloads", exist_ok=True)
            
            download_result = client.download_file(file_id, download_path)
            
            if download_result.get('success'):
                # 验证哈希
                original_hash = calculate_file_hash(test_file)
                downloaded_hash = calculate_file_hash(download_path)
                
                if original_hash == downloaded_hash:
                    print(f"✓ 文件完整性验证通过")
                    print(f"  原始哈希: {original_hash[:16]}...")
                    print(f"  下载哈希: {downloaded_hash[:16]}...")
                else:
                    print(f"✗ 文件完整性验证失败")
                    print(f"  原始哈希: {original_hash[:16]}...")
                    print(f"  下载哈希: {downloaded_hash[:16]}...")
                    return False
                
                # 清理下载的文件
                if os.path.exists(download_path):
                    os.remove(download_path)
            else:
                print(f"✗ 下载失败: {download_result.get('error')}")
                return False
        else:
            print(f"✗ 上传失败: {result.get('error')}")
            return False
        
        print("\n✅ 测试通过: 大文件块级上传")
        return True
    
    finally:
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)


def test_partial_duplicate_content(client):
    """测试3: 部分重复内容的文件"""
    print_section("测试 3: 部分重复内容的文件")
    
    # 创建两个部分重复的文件
    test_file1 = "test_block_partial1.bin"
    test_file2 = "test_block_partial2.bin"
    
    # 文件1: AAABBB (6MB)
    with open(test_file1, 'wb') as f:
        chunk_a = b'A' * (1024 * 1024)
        chunk_b = b'B' * (1024 * 1024)
        for _ in range(3):
            f.write(chunk_a)
        for _ in range(3):
            f.write(chunk_b)
    
    print(f"✓ 生成测试文件: {test_file1} (6 MB, pattern=AAABBB)")
    
    # 文件2: BBBCCC (6MB) - 与文件1共享BBB部分
    with open(test_file2, 'wb') as f:
        chunk_b = b'B' * (1024 * 1024)
        chunk_c = b'C' * (1024 * 1024)
        for _ in range(3):
            f.write(chunk_b)
        for _ in range(3):
            f.write(chunk_c)
    
    print(f"✓ 生成测试文件: {test_file2} (6 MB, pattern=BBBCCC)")
    
    try:
        # 上传文件1
        print("\n上传文件1:")
        result1 = client.upload_file(
            test_file1,
            enable_block_deduplication=True,
            chunk_size=1 * 1024 * 1024  # 1MB块
        )
        
        if not result1.get('success'):
            print(f"✗ 上传文件1失败: {result1.get('error')}")
            return False
        
        print(f"✓ 文件1上传成功")
        
        # 上传文件2（应该复用BBB部分的块）
        print("\n上传文件2（应该复用部分块）:")
        result2 = client.upload_file(
            test_file2,
            enable_block_deduplication=True,
            chunk_size=1 * 1024 * 1024
        )
        
        if result2.get('success'):
            print(f"✓ 文件2上传成功")
            print(f"  预期: 应该有50%的块被去重（BBB部分）")
        else:
            print(f"✗ 上传文件2失败: {result2.get('error')}")
            return False
        
        print("\n✅ 测试通过: 部分重复内容的文件")
        return True
    
    finally:
        # 清理测试文件
        if os.path.exists(test_file1):
            os.remove(test_file1)
        if os.path.exists(test_file2):
            os.remove(test_file2)


def test_deduplication_stats(client):
    """测试4: 查看去重统计"""
    print_section("测试 4: 块级去重统计")
    
    try:
        import requests
        headers = client._get_headers()
        
        response = client.session.get(
            f"{client.base_url}/api/block-upload/stats",
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                stats = result['stats']
                
                print("\n块级去重统计:")
                print(f"  总数据块数: {stats['total_blocks']}")
                print(f"  总引用次数: {stats['total_references']}")
                print(f"  总大小: {stats['total_size_mb']:.2f} MB")
                print(f"  节省空间: {stats['saved_space_mb']:.2f} MB")
                print(f"  去重率: {stats['deduplication_ratio']}%")
                print(f"  压缩块数: {stats['compressed_blocks']}")
                
                print("\n✅ 测试通过: 块级去重统计")
                return True
            else:
                print(f"✗ 获取统计失败")
                return False
        else:
            print(f"✗ API调用失败: {response.status_code}")
            return False
    
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 80)
    print("块级去重功能测试")
    print("=" * 80)
    
    # 初始化客户端
    auth_client = AuthClient()
    
    # 登录或注册测试用户
    username = "testuser_block"
    password = "testpass123"
    
    print(f"\n登录用户: {username}")
    login_result = auth_client.login(username, password)
    
    if not login_result:
        print(f"用户不存在，尝试注册...")
        register_result = auth_client.register(username, password)
        if register_result:
            print(f"✓ 注册成功")
            login_result = auth_client.login(username, password)
        else:
            print(f"✗ 注册失败")
            return
    
    if not login_result:
        print(f"✗ 登录失败")
        return
    
    print(f"✓ 登录成功")
    
    # 创建客户端
    client = CloudDriveClient(auth_client=auth_client)
    
    # 运行测试
    results = {}
    
    results['基本块级去重功能'] = test_basic_block_deduplication(client)
    results['大文件块级上传'] = test_large_file_block_upload(client)
    results['部分重复内容'] = test_partial_duplicate_content(client)
    results['块级去重统计'] = test_deduplication_stats(client)
    
    # 打印测试结果汇总
    print_section("测试结果汇总")
    
    passed = 0
    failed = 0
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "✗ 失败"
        print(f"  {status}: {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed}/{len(results)} 通过")
    
    if failed == 0:
        print("\n🎉 所有测试通过！块级去重功能正常工作！")
    else:
        print(f"\n⚠️  有 {failed} 个测试失败，请检查。")


if __name__ == "__main__":
    main()

