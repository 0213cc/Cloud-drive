"""
压缩功能调试脚本 - 详细检查压缩流程
"""
import os
import sys
import requests
import tempfile

# 添加client目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client', 'src'))

from client import CloudDriveClient
from auth_client import AuthClient
from config import config


def generate_test_file(size_mb=10):
    """生成可压缩的测试文件"""
    filename = f"test_compress_{size_mb}mb.txt"
    
    # 生成重复内容（高度可压缩）
    line = "This is a test line for compression testing. " * 10 + "\n"
    lines_needed = int((size_mb * 1024 * 1024) / len(line))
    
    with open(filename, 'w', encoding='utf-8') as f:
        for _ in range(lines_needed):
            f.write(line)
    
    actual_size = os.path.getsize(filename)
    print(f"✓ 生成测试文件: {filename}")
    print(f"  大小: {actual_size / 1024 / 1024:.2f} MB")
    
    return filename, actual_size


def test_compression_api_direct():
    """直接测试API，查看压缩参数"""
    print("\n" + "=" * 80)
    print("测试 1: 直接API调用（带enable_compression参数）")
    print("=" * 80)
    
    # 生成测试文件
    filename, file_size = generate_test_file(10)
    
    # 获取认证token
    auth_client = AuthClient(config.API_BASE_URL)
    if not auth_client.is_authenticated():
        print("❌ 未登录，请先运行: python client/client.py login")
        return
    
    headers = auth_client.get_auth_header()
    
    # 上传文件 - 明确启用压缩
    url = f"{config.API_BASE_URL}/api/files/upload"
    
    print(f"\n上传URL: {url}")
    print(f"参数: path=/, enable_compression=true")
    
    with open(filename, 'rb') as f:
        files = {'file': (filename, f)}
        params = {
            'path': '/',
            'enable_compression': 'true'  # 明确传递
        }
        
        print(f"\n发送请求...")
        response = requests.post(url, files=files, params=params, headers=headers)
    
    print(f"响应状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        file_info = result.get('file_info', {})
        
        print(f"\n✓ 上传成功")
        print(f"  文件ID: {file_info.get('id')}")
        print(f"  文件名: {file_info.get('filename')}")
        print(f"  原始大小: {file_info.get('size') / 1024 / 1024:.2f} MB")
        print(f"  是否压缩: {file_info.get('is_compressed')}")
        
        if file_info.get('is_compressed'):
            compressed_size = file_info.get('compressed_size', 0)
            compression_ratio = file_info.get('compression_ratio', 0)
            print(f"  压缩后大小: {compressed_size / 1024 / 1024:.2f} MB")
            print(f"  压缩率: {compression_ratio}%")
            print(f"  节省空间: {(file_info.get('size') - compressed_size) / 1024 / 1024:.2f} MB")
            print(f"\n✅ 压缩功能正常工作！")
        else:
            print(f"\n❌ 文件未被压缩！")
            print(f"  可能原因:")
            print(f"    1. 文件太小（< 1KB）")
            print(f"    2. 文件类型不适合压缩")
            print(f"    3. 后端压缩逻辑有问题")
        
        return file_info.get('id')
    else:
        print(f"\n❌ 上传失败")
        print(f"错误: {response.text}")
        return None


def test_compression_client():
    """测试客户端上传（不带enable_compression参数）"""
    print("\n" + "=" * 80)
    print("测试 2: 客户端上传（默认参数）")
    print("=" * 80)
    
    # 生成测试文件
    filename, file_size = generate_test_file(10)
    
    # 使用客户端上传
    client = CloudDriveClient()
    
    if not client.auth_client.is_authenticated():
        print("❌ 未登录，请先运行: python client/client.py login")
        return
    
    print(f"\n使用CloudDriveClient上传...")
    result = client.upload_file(filename, remote_path="/", show_progress=False)
    
    if result.get('file_info'):
        file_info = result['file_info']
        file_id = file_info.get('id')
        
        print(f"\n✓ 上传成功")
        print(f"  文件ID: {file_id}")
        print(f"  是否压缩: {file_info.get('is_compressed')}")
        
        if file_info.get('is_compressed'):
            print(f"  压缩率: {file_info.get('compression_ratio')}%")
            print(f"\n✅ 客户端压缩功能正常！")
        else:
            print(f"\n❌ 客户端上传时文件未被压缩！")
            print(f"  这说明客户端没有正确传递enable_compression参数")
        
        return file_id
    else:
        print(f"\n❌ 上传失败: {result.get('error')}")
        return None


def check_backend_logs():
    """检查后端日志"""
    print("\n" + "=" * 80)
    print("提示: 检查后端日志")
    print("=" * 80)
    print("\n在后端终端查看日志，确认:")
    print("  1. 是否收到 enable_compression 参数")
    print("  2. should_compress() 返回值")
    print("  3. 压缩过程是否执行")
    print("  4. 是否有错误信息")
    print("\n如果后端使用uvicorn运行，应该能看到详细的请求日志")


def cleanup_test_files():
    """清理测试文件"""
    import glob
    for f in glob.glob("test_compress_*.txt"):
        try:
            os.remove(f)
            print(f"✓ 删除测试文件: {f}")
        except:
            pass


def main():
    """主函数"""
    print("=" * 80)
    print("压缩功能调试工具")
    print("=" * 80)
    print("\n这个脚本会:")
    print("  1. 生成10MB可压缩测试文件")
    print("  2. 使用两种方式上传（直接API vs 客户端）")
    print("  3. 对比压缩效果")
    print("  4. 帮助定位问题")
    
    try:
        # 测试1: 直接API调用
        file_id_1 = test_compression_api_direct()
        
        # 测试2: 客户端调用
        file_id_2 = test_compression_client()
        
        # 显示后端日志提示
        check_backend_logs()
        
        print("\n" + "=" * 80)
        print("测试完成")
        print("=" * 80)
        
        if file_id_1 and file_id_2:
            print(f"\n上传的文件ID:")
            print(f"  直接API: {file_id_1}")
            print(f"  客户端: {file_id_2}")
            print(f"\n可以使用以下命令查看文件详情:")
            print(f"  python client/client.py info {file_id_1}")
            print(f"  python client/client.py info {file_id_2}")
        
        # 询问是否清理
        print(f"\n是否删除测试文件? (y/n): ", end="")
        if input().lower() == 'y':
            cleanup_test_files()
        
    except KeyboardInterrupt:
        print("\n\n中断测试")
        cleanup_test_files()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

