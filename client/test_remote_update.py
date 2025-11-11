"""
测试远程文件更新同步
"""
import os
import time
from pathlib import Path

def main():
    print("=" * 60)
    print("  测试远程文件更新同步")
    print("=" * 60)
    print()
    print("测试场景：")
    print("  1. 本地同步文件夹有文件 test_update.txt")
    print("  2. 从另一客户端上传同名但内容不同的文件")
    print("  3. 检查本地文件是否自动更新")
    print()
    print("前提条件：")
    print("  - 同步客户端正在运行（另一个窗口）")
    print("  - 后端服务正常运行")
    print()
    input("按Enter开始测试...")
    
    sync_folder = Path("sync_folder")
    test_file = sync_folder / "test_update.txt"
    
    # 步骤1：在同步文件夹创建文件
    print("\n步骤1：在同步文件夹创建文件")
    print("=" * 60)
    test_file.write_text("Version 1: Original content from sync folder\n")
    print(f"✓ 创建文件: {test_file}")
    print(f"  内容: Version 1")
    
    print("\n等待5秒，让文件上传...")
    for i in range(5, 0, -1):
        print(f"  {i}秒...", end='\r')
        time.sleep(1)
    print("  完成！    ")
    
    # 步骤2：使用普通客户端上传同名文件（模拟另一设备）
    print("\n步骤2：从'另一设备'上传同名但内容不同的文件")
    print("=" * 60)
    
    # 创建临时文件
    temp_file = Path("temp_version2.txt")
    temp_file.write_text("Version 2: Updated content from another device\nThis is different!\n")
    print(f"✓ 创建临时文件: {temp_file}")
    print(f"  内容: Version 2 (不同内容)")
    
    # 使用普通客户端上传
    print("\n  使用普通客户端上传...")
    from client import CloudDriveClient
    from config import config
    
    client = CloudDriveClient(config.API_BASE_URL)
    result = client.upload_file(str(temp_file), remote_path="/", show_progress=False)
    
    if result.get('success'):
        file_id = result['file_info']['id']
        print(f"  ✓ 上传成功，文件ID: {file_id}")
        
        # 删除服务器上的原文件，上传为同名
        print(f"  正在替换服务器上的 test_update.txt...")
        
        # 简化：直接删除旧的，重命名新的（实际应该用API重命名）
        # 这里我们重新上传同名文件
        result2 = client.upload_file(str(temp_file), remote_path="/", show_progress=False)
        
        # 实际操作：手动重命名
        print("\n  ⚠️  需要手动操作：")
        print(f"     1. 在浏览器打开: {config.API_BASE_URL}/docs")
        print(f"     2. 使用 DELETE /api/files/delete 删除旧的 test_update.txt")
        print(f"     3. 重新上传 temp_version2.txt 为 test_update.txt")
        print()
        print("  或者直接用客户端：")
        print(f"     python client.py delete <原文件ID>")
        print(f"     python client.py upload temp_version2.txt --path /")
        print("     手动重命名上传的文件为 test_update.txt")
    
    # 清理临时文件
    temp_file.unlink()
    
    print("\n步骤3：等待同步客户端检测到更新")
    print("=" * 60)
    print("  同步客户端每30秒拉取一次更新")
    print("  或者重启同步客户端立即拉取")
    print()
    
    for i in range(30, 0, -1):
        print(f"  等待... {i}秒", end='\r')
        time.sleep(1)
    print("  " * 20)
    
    # 步骤4：检查本地文件内容
    print("\n步骤4：检查本地文件是否更新")
    print("=" * 60)
    
    if test_file.exists():
        current_content = test_file.read_text()
        print(f"当前文件内容:")
        print("-" * 40)
        print(current_content)
        print("-" * 40)
        
        if "Version 2" in current_content:
            print("\n✅ 测试成功！本地文件已自动更新为远程版本")
        elif "Version 1" in current_content:
            print("\n❌ 测试失败：本地文件未更新")
            print("   可能原因：")
            print("   1. 同步客户端未检测到更新（还未到30秒）")
            print("   2. 服务器上传的文件名不是 test_update.txt")
            print("   3. 修复代码未生效")
        else:
            print("\n⚠️  未知状态")
    else:
        print("❌ 测试文件不存在")
    
    # 检查是否有冲突副本
    print("\n检查冲突副本...")
    conflict_files = list(sync_folder.glob("test_update*conflict*.txt"))
    if conflict_files:
        print(f"✓ 发现冲突副本: {len(conflict_files)} 个")
        for cf in conflict_files:
            print(f"  - {cf.name}")
    else:
        print("  无冲突副本（远程单方面修改）")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

