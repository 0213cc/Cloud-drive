"""
测试脚本 - 创建测试文件并上传
"""
import os
import sys

def create_test_files():
    """创建不同大小的测试文件"""
    
    print("📝 创建测试文件...")
    
    test_files = [
        ("small_file.txt", 1024),           # 1KB
        ("medium_file.txt", 10 * 1024 * 1024),  # 10MB
        ("large_file.bin", 150 * 1024 * 1024),  # 150MB (会触发多线程)
    ]
    
    for filename, size in test_files:
        if os.path.exists(filename):
            print(f"⏭️  跳过: {filename} (已存在)")
            continue
            
        print(f"✏️  创建: {filename} ({size / 1024 / 1024:.2f} MB)")
        
        with open(filename, 'wb') as f:
            # 写入随机数据
            remaining = size
            chunk_size = 1024 * 1024  # 1MB
            
            while remaining > 0:
                write_size = min(chunk_size, remaining)
                f.write(os.urandom(write_size))
                remaining -= write_size
    
    print("\n✅ 测试文件创建完成！")
    print("\n📤 现在可以使用客户端上传：")
    print("   cd client")
    print("   python client.py upload ../small_file.txt")
    print("   python client.py upload ../medium_file.txt")
    print("   python client.py upload ../large_file.bin  # 多线程上传")


if __name__ == "__main__":
    try:
        create_test_files()
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)

