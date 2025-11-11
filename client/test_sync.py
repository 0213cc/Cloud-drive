"""
自动同步功能测试脚本
"""
import os
import time
import shutil
from pathlib import Path

def print_step(step, description):
    """打印测试步骤"""
    print("\n" + "=" * 60)
    print(f"步骤 {step}: {description}")
    print("=" * 60)

def wait_for_sync(seconds=3):
    """等待同步完成"""
    for i in range(seconds, 0, -1):
        print(f"等待同步... {i}秒", end='\r')
        time.sleep(1)
    print(" " * 40, end='\r')

def main():
    """主测试流程"""
    print("\n" * 2)
    print("=" * 60)
    print("     云盘自动同步功能测试")
    print("=" * 60)
    print()
    print("前提条件检查：")
    print("  1. 后端服务已启动（本地或远程）")
    print("  2. 同步客户端正在运行（另一个窗口）")
    print("  3. 已安装所有依赖")
    print()
    input("按Enter继续...")
    
    # 测试文件夹
    sync_folder = Path("sync_folder")
    
    if not sync_folder.exists():
        print(f"\n错误: 同步文件夹不存在: {sync_folder}")
        print("请先启动同步客户端：python sync_client.py")
        return
    
    # 测试1：创建文件
    print_step(1, "测试文件创建同步")
    test_file1 = sync_folder / "test_file_1.txt"
    print(f"创建文件: {test_file1}")
    test_file1.write_text("This is test file 1\nCreated for sync test")
    print("✓ 文件已创建")
    wait_for_sync(3)
    print("✓ 查看同步日志确认文件已上传")
    
    # 测试2：修改文件
    print_step(2, "测试文件修改同步")
    print(f"修改文件: {test_file1}")
    test_file1.write_text("This is test file 1\nModified content\nNew line added")
    print("✓ 文件已修改")
    wait_for_sync(3)
    print("✓ 查看同步日志确认文件已重新上传")
    
    # 测试3：创建多个文件
    print_step(3, "测试多文件同步")
    for i in range(2, 5):
        test_file = sync_folder / f"test_file_{i}.txt"
        print(f"创建文件: {test_file}")
        test_file.write_text(f"Test file {i}\nContent line 1\nContent line 2")
    print("✓ 已创建3个文件")
    wait_for_sync(5)
    print("✓ 查看同步日志确认所有文件已上传")
    
    # 测试4：创建目录和文件
    print_step(4, "测试目录同步")
    test_dir = sync_folder / "test_documents"
    test_dir.mkdir(exist_ok=True)
    print(f"创建目录: {test_dir}")
    
    doc_file = test_dir / "report.txt"
    print(f"创建文件: {doc_file}")
    doc_file.write_text("Important Report\n\nSection 1\nSection 2")
    print("✓ 目录和文件已创建")
    wait_for_sync(3)
    print("✓ 查看同步日志确认目录文件已上传")
    
    # 测试5：文件重命名
    print_step(5, "测试文件重命名")
    old_name = sync_folder / "test_file_2.txt"
    new_name = sync_folder / "test_file_renamed.txt"
    if old_name.exists():
        print(f"重命名: {old_name} -> {new_name}")
        old_name.rename(new_name)
        print("✓ 文件已重命名")
        wait_for_sync(3)
        print("✓ 查看同步日志确认重命名已同步")
    
    # 测试6：文件删除
    print_step(6, "测试文件删除")
    delete_file = sync_folder / "test_file_3.txt"
    if delete_file.exists():
        print(f"删除文件: {delete_file}")
        delete_file.unlink()
        print("✓ 文件已删除")
        wait_for_sync(3)
        print("✓ 查看同步日志确认删除已同步")
    
    # 测试7：批量操作
    print_step(7, "测试批量文件操作")
    batch_dir = sync_folder / "batch_test"
    batch_dir.mkdir(exist_ok=True)
    print(f"创建目录: {batch_dir}")
    
    for i in range(1, 6):
        batch_file = batch_dir / f"batch_{i}.txt"
        batch_file.write_text(f"Batch file {i}")
        print(f"  创建: batch_{i}.txt")
    
    print("✓ 已创建5个批量文件")
    wait_for_sync(5)
    print("✓ 查看同步日志确认批量上传")
    
    # 完成
    print("\n" + "=" * 60)
    print("     测试完成！")
    print("=" * 60)
    print("\n验证步骤：")
    print("  1. 查看 sync.log 日志文件")
    print("  2. 使用命令查看远程文件：")
    print("     python client.py list")
    print("  3. 在浏览器查看：")
    print("     http://localhost:8000/docs")
    print("  4. 同步状态检查：")
    print("     python sync_client.py --status")
    print()
    print("清理测试文件？")
    cleanup = input("输入 'yes' 清理测试文件，或按Enter保留: ").strip().lower()
    
    if cleanup == 'yes':
        print("\n清理测试文件...")
        for item in sync_folder.iterdir():
            if item.name.startswith('test_') or item.name == 'batch_test':
                if item.is_file():
                    item.unlink()
                    print(f"  删除文件: {item.name}")
                elif item.is_dir():
                    shutil.rmtree(item)
                    print(f"  删除目录: {item.name}")
        print("✓ 清理完成")
        wait_for_sync(3)
        print("✓ 删除操作已同步到服务器")
    
    print("\n测试结束！")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试被中断")
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()

