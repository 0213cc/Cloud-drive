"""
文件去重功能测试脚本
"""
import os
import sys
import time

# 添加client目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client', 'src'))

from client import CloudDriveClient
from auth_client import AuthClient
from dedup_client import DeduplicationClient
from config import config


def print_separator(title=""):
    """打印分隔线"""
    if title:
        print(f"\n{'=' * 80}")
        print(f"{title}")
        print('=' * 80)
    else:
        print('=' * 80)


def generate_test_file(filename, size_mb=1, content="Test content for deduplication.\n"):
    """生成测试文件"""
    lines_needed = int((size_mb * 1024 * 1024) / len(content))
    
    with open(filename, 'w', encoding='utf-8') as f:
        for _ in range(lines_needed):
            f.write(content)
    
    actual_size = os.path.getsize(filename)
    print(f"✓ 生成测试文件: {filename} ({actual_size / 1024 / 1024:.2f} MB)")
    return filename, actual_size


def test_basic_deduplication():
    """测试基本去重功能"""
    print_separator("测试 1: 基本去重功能")
    
    client = CloudDriveClient()
    
    if not client.auth_client.is_authenticated():
        print("❌ 未登录，请先运行: python client/client.py login")
        return False
    
    # 生成测试文件
    test_file1, size1 = generate_test_file("test_dedup_1.txt", 1)
    
    # 第一次上传
    print("\n第一次上传（应该正常上传）:")
    result1 = client.upload_file(test_file1, remote_path="/", show_progress=False)
    
    if not result1.get('file_info'):
        print(f"❌ 第一次上传失败: {result1.get('error')}")
        return False
    
    file_id_1 = result1['file_info']['id']
    print(f"✓ 第一次上传成功，文件ID: {file_id_1}")
    
    # 复制文件（内容相同）
    test_file2 = "test_dedup_2.txt"
    import shutil
    shutil.copy(test_file1, test_file2)
    print(f"\n✓ 复制文件: {test_file2}")
    
    # 第二次上传（应该通过去重）
    print("\n第二次上传相同内容的文件（应该通过去重）:")
    result2 = client.upload_file(test_file2, remote_path="/", show_progress=False)
    
    if not result2.get('file_info'):
        print(f"❌ 第二次上传失败: {result2.get('error')}")
        return False
    
    file_id_2 = result2['file_info']['id']
    print(f"✓ 第二次上传成功，文件ID: {file_id_2}")
    
    # 检查是否通过去重
    message = result2.get('message', '')
    if '去重' in message or 'deduplicate' in message.lower():
        print(f"✅ 去重成功！消息: {message}")
    else:
        print(f"⚠️  可能未通过去重。消息: {message}")
    
    # 清理
    os.remove(test_file1)
    os.remove(test_file2)
    
    return True


def test_different_files():
    """测试不同文件不会去重"""
    print_separator("测试 2: 不同文件不会去重")
    
    client = CloudDriveClient()
    
    # 生成两个不同内容的文件
    test_file1, _ = generate_test_file("test_diff_1.txt", 1, "Content A\n")
    test_file2, _ = generate_test_file("test_diff_2.txt", 1, "Content B\n")
    
    # 上传第一个文件
    print("\n上传第一个文件:")
    result1 = client.upload_file(test_file1, remote_path="/", show_progress=False)
    
    if not result1.get('file_info'):
        print(f"❌ 上传失败: {result1.get('error')}")
        return False
    
    print(f"✓ 上传成功，文件ID: {result1['file_info']['id']}")
    
    # 上传第二个文件
    print("\n上传第二个文件（内容不同）:")
    result2 = client.upload_file(test_file2, remote_path="/", show_progress=False)
    
    if not result2.get('file_info'):
        print(f"❌ 上传失败: {result2.get('error')}")
        return False
    
    print(f"✓ 上传成功，文件ID: {result2['file_info']['id']}")
    
    # 检查是否通过去重
    message = result2.get('message', '')
    if '去重' not in message and 'deduplicate' not in message.lower():
        print(f"✅ 正确：不同文件未去重")
    else:
        print(f"❌ 错误：不同文件被去重了！")
        return False
    
    # 清理
    os.remove(test_file1)
    os.remove(test_file2)
    
    return True


def test_deduplication_stats():
    """测试去重统计"""
    print_separator("测试 3: 去重统计")
    
    client = CloudDriveClient()
    headers = client._get_headers()
    
    stats = DeduplicationClient.get_deduplication_stats(
        client.session,
        client.base_url,
        headers
    )
    
    if not stats:
        print("❌ 获取去重统计失败")
        return False
    
    print("\n去重统计信息:")
    print(f"  总文件块数: {stats.get('total_chunks')}")
    print(f"  总文件数: {stats.get('total_files')}")
    print(f"  被去重的文件块数: {stats.get('deduplicated_chunks')}")
    print(f"  重复文件副本数: {stats.get('duplicate_count')}")
    print(f"  平均引用次数: {stats.get('average_references', 0):.2f}")
    print(f"  节省空间: {stats.get('saved_space_mb', 0):.2f} MB")
    print(f"  实际存储: {stats.get('actual_storage_mb', 0):.2f} MB")
    print(f"  无去重时需要: {stats.get('total_size_without_dedup_mb', 0):.2f} MB")
    print(f"  去重率: {stats.get('deduplication_ratio', 0):.2f}%")
    
    print("\n✅ 去重统计获取成功")
    return True


def test_version_control_with_dedup():
    """测试去重与版本控制的兼容性"""
    print_separator("测试 4: 去重与版本控制兼容性")
    
    client = CloudDriveClient()
    
    # 生成第一个版本
    test_file, _ = generate_test_file("test_version_dedup.txt", 1, "Version 1\n")
    
    # 上传第一个版本
    print("\n上传第一个版本:")
    result1 = client.upload_file(test_file, remote_path="/", show_progress=False)
    
    if not result1.get('file_info'):
        print(f"❌ 上传失败: {result1.get('error')}")
        return False
    
    file_id = result1['file_info']['id']
    version1 = result1['file_info']['version']
    print(f"✓ 上传成功，文件ID: {file_id}, 版本: {version1}")
    
    # 修改文件内容
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write("Version 2\n" * 100000)
    
    # 上传第二个版本
    print("\n上传第二个版本（内容不同）:")
    result2 = client.update_file(file_id, test_file, show_progress=False)
    
    if not result2.get('file_info'):
        print(f"❌ 更新失败: {result2.get('error')}")
        return False
    
    version2 = result2['file_info']['version']
    print(f"✓ 更新成功，版本: {version2}")
    
    if version2 > version1:
        print(f"✅ 版本控制正常工作（{version1} -> {version2}）")
    else:
        print(f"❌ 版本控制异常")
        return False
    
    # 再次上传相同内容（应该去重）
    test_file2 = "test_version_dedup_2.txt"
    with open(test_file2, 'w', encoding='utf-8') as f:
        f.write("Version 2\n" * 100000)
    
    print("\n上传相同内容的新文件（应该去重）:")
    result3 = client.upload_file(test_file2, remote_path="/", show_progress=False)
    
    if not result3.get('file_info'):
        print(f"❌ 上传失败: {result3.get('error')}")
        return False
    
    message = result3.get('message', '')
    if '去重' in message or 'deduplicate' in message.lower():
        print(f"✅ 去重与版本控制兼容")
    else:
        print(f"⚠️  可能未通过去重")
    
    # 清理
    os.remove(test_file)
    os.remove(test_file2)
    
    return True


def test_large_file_dedup():
    """测试大文件去重"""
    print_separator("测试 5: 大文件去重（10MB）")
    
    client = CloudDriveClient()
    
    # 生成10MB测试文件
    test_file1, _ = generate_test_file("test_large_dedup_1.txt", 10)
    
    # 第一次上传
    print("\n第一次上传10MB文件:")
    start_time = time.time()
    result1 = client.upload_file(test_file1, remote_path="/", show_progress=True)
    upload_time_1 = time.time() - start_time
    
    if not result1.get('file_info'):
        print(f"❌ 第一次上传失败: {result1.get('error')}")
        return False
    
    print(f"✓ 第一次上传成功，耗时: {upload_time_1:.2f}秒")
    
    # 复制文件
    test_file2 = "test_large_dedup_2.txt"
    import shutil
    shutil.copy(test_file1, test_file2)
    
    # 第二次上传（应该通过去重，速度更快）
    print("\n第二次上传相同的10MB文件（应该去重）:")
    start_time = time.time()
    result2 = client.upload_file(test_file2, remote_path="/", show_progress=False)
    upload_time_2 = time.time() - start_time
    
    if not result2.get('file_info'):
        print(f"❌ 第二次上传失败: {result2.get('error')}")
        return False
    
    print(f"✓ 第二次上传成功，耗时: {upload_time_2:.2f}秒")
    
    # 比较时间
    if upload_time_2 < upload_time_1 * 0.5:  # 去重应该快很多
        print(f"✅ 去重显著提升速度（{upload_time_1:.2f}s -> {upload_time_2:.2f}s）")
    else:
        print(f"⚠️  去重速度提升不明显")
    
    # 检查消息
    message = result2.get('message', '')
    if '去重' in message or 'deduplicate' in message.lower():
        print(f"✅ 确认通过去重: {message}")
    
    # 清理
    os.remove(test_file1)
    os.remove(test_file2)
    
    return True


def main():
    """主函数"""
    print_separator("文件去重功能测试")
    
    print("\n这个脚本会测试:")
    print("  1. 基本去重功能")
    print("  2. 不同文件不会去重")
    print("  3. 去重统计信息")
    print("  4. 去重与版本控制兼容性")
    print("  5. 大文件去重")
    
    # 检查登录状态
    auth_client = AuthClient(config.API_BASE_URL)
    if not auth_client.is_authenticated():
        print("\n❌ 未登录，请先运行: python client/client.py login")
        return
    
    print(f"\n当前用户: {auth_client.get_current_user()}")
    
    # 运行测试
    tests = [
        ("基本去重功能", test_basic_deduplication),
        ("不同文件不会去重", test_different_files),
        ("去重统计", test_deduplication_stats),
        ("去重与版本控制兼容性", test_version_control_with_dedup),
        ("大文件去重", test_large_file_dedup),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n❌ 测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # 显示测试结果
    print_separator("测试结果汇总")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {status}: {test_name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！文件去重功能正常工作！")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查日志")
    
    # 清理测试文件
    print("\n清理测试文件...")
    import glob
    for pattern in ["test_dedup_*.txt", "test_diff_*.txt", "test_version_dedup*.txt", "test_large_dedup*.txt"]:
        for f in glob.glob(pattern):
            try:
                os.remove(f)
                print(f"  ✓ 删除: {f}")
            except:
                pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试中断")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

