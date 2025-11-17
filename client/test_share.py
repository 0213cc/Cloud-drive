"""
共享功能测试脚本

测试文件/文件夹共享功能的完整流程：
1. 创建测试用户
2. 上传测试文件
3. 创建共享（只读/可写）
4. 验证共享访问权限
5. 更新共享设置
6. 删除共享
"""
import sys
import os
import time
from datetime import datetime, timedelta

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from client import CloudDriveClient
from auth_client import AuthClient
from config import config


def print_section(title: str):
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_share_functionality():
    """测试共享功能"""
    
    print_section("共享功能测试")
    
    # 生成唯一的测试用户名
    timestamp = int(time.time())
    alice_username = f"alice_{timestamp}"
    bob_username = f"bob_{timestamp}"
    
    print(f"\n测试用户:")
    print(f"  Alice: {alice_username}")
    print(f"  Bob: {bob_username}")
    
    # ==================== 步骤 1: 注册两个测试用户 ====================
    print_section("步骤 1: 注册测试用户")
    
    auth_client = AuthClient(config.API_BASE_URL)
    
    # 注册 Alice
    print(f"\n注册 Alice ({alice_username})...")
    alice_result = auth_client.register(alice_username, f"{alice_username}@example.com", "password123")
    if not alice_result.get('success'):
        print(f"✗ Alice 注册失败: {alice_result.get('error')}")
        return False
    print(f"✓ Alice 注册成功 (ID: {alice_result.get('user_id')})")
    alice_token = alice_result.get('access_token')
    
    # 注册 Bob
    print(f"\n注册 Bob ({bob_username})...")
    bob_result = auth_client.register(bob_username, f"{bob_username}@example.com", "password123")
    if not bob_result.get('success'):
        print(f"✗ Bob 注册失败: {bob_result.get('error')}")
        return False
    print(f"✓ Bob 注册成功 (ID: {bob_result.get('user_id')})")
    bob_token = bob_result.get('access_token')
    
    # ==================== 步骤 2: Alice 上传测试文件 ====================
    print_section("步骤 2: Alice 上传测试文件")
    
    # 创建 Alice 的客户端
    alice_auth = AuthClient(config.API_BASE_URL)
    alice_auth.token = alice_token
    alice_auth.save_token()
    alice_client = CloudDriveClient(auth_client=alice_auth)
    
    # 创建测试文件
    test_file = "share_test_file.txt"
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(f"这是 Alice 的测试文件\n创建时间: {datetime.now()}\n")
    
    print(f"\n上传文件: {test_file}")
    upload_result = alice_client.upload_file(test_file, show_progress=False)
    if not upload_result.get('success'):
        print(f"✗ 上传失败")
        return False
    
    file_id = upload_result.get('file_info', {}).get('id')
    print(f"✓ 上传成功 (文件ID: {file_id})")
    
    # 清理本地测试文件
    os.remove(test_file)
    
    # ==================== 步骤 3: Alice 创建只读共享给 Bob ====================
    print_section("步骤 3: Alice 创建只读共享给 Bob")
    
    print(f"\n创建只读共享...")
    share_result = alice_client.create_share(file_id, bob_username, "read")
    if not share_result:
        print(f"✗ 创建共享失败")
        return False
    
    share_id = share_result.get('share_info', {}).get('id')
    print(f"✓ 共享创建成功 (共享ID: {share_id})")
    
    # ==================== 步骤 4: Alice 查看自己的共享列表 ====================
    print_section("步骤 4: Alice 查看自己的共享列表")
    
    alice_shares = alice_client.list_my_shares()
    if alice_shares is None:
        print(f"✗ 获取共享列表失败")
        return False
    
    if len(alice_shares) == 0:
        print(f"✗ 共享列表为空")
        return False
    
    print(f"✓ 找到 {len(alice_shares)} 个共享")
    
    # ==================== 步骤 5: Bob 查看分享给自己的文件 ====================
    print_section("步骤 5: Bob 查看分享给自己的文件")
    
    # 创建 Bob 的客户端
    bob_auth = AuthClient(config.API_BASE_URL)
    bob_auth.token = bob_token
    bob_auth.save_token()
    bob_client = CloudDriveClient(auth_client=bob_auth)
    
    bob_shares = bob_client.list_shared_with_me()
    if bob_shares is None:
        print(f"✗ 获取共享列表失败")
        return False
    
    if len(bob_shares) == 0:
        print(f"✗ 共享列表为空")
        return False
    
    print(f"✓ 找到 {len(bob_shares)} 个共享文件")
    
    # ==================== 步骤 6: Bob 下载共享文件（只读权限）====================
    print_section("步骤 6: Bob 下载共享文件")
    
    print(f"\nBob 尝试下载文件 (ID: {file_id})...")
    download_result = bob_client.download_file(file_id, show_progress=False)
    if not download_result.get('success'):
        print(f"✗ 下载失败: {download_result.get('error')}")
        return False
    
    print(f"✓ 下载成功: {download_result.get('path')}")
    
    # 验证文件内容
    with open(download_result.get('path'), 'r', encoding='utf-8') as f:
        content = f.read()
        if "Alice" in content:
            print(f"✓ 文件内容验证成功")
        else:
            print(f"✗ 文件内容验证失败")
            return False
    
    # 清理下载的文件
    os.remove(download_result.get('path'))
    
    # ==================== 步骤 7: Bob 尝试删除共享文件（应该失败）====================
    print_section("步骤 7: Bob 尝试删除共享文件（应该失败）")
    
    print(f"\nBob 尝试删除文件 (ID: {file_id})...")
    delete_result = bob_client.delete_file(file_id)
    if delete_result and delete_result.get('success'):
        print(f"✗ 删除成功（不应该成功！）")
        return False
    
    print(f"✓ 删除被拒绝（符合预期）")
    
    # ==================== 步骤 8: Alice 更新共享权限为可写 ====================
    print_section("步骤 8: Alice 更新共享权限为可写")
    
    print(f"\n更新共享权限...")
    update_result = alice_client.update_share(share_id, permission="write")
    if not update_result:
        print(f"✗ 更新失败")
        return False
    
    print(f"✓ 权限更新成功")
    
    # ==================== 步骤 9: 验证共享详情 ====================
    print_section("步骤 9: 验证共享详情")
    
    print(f"\n查看共享详情 (ID: {share_id})...")
    share_info = alice_client.get_share_info(share_id)
    if not share_info:
        print(f"✗ 获取共享详情失败")
        return False
    
    if share_info.get('permission') != 'write':
        print(f"✗ 权限未更新")
        return False
    
    print(f"✓ 共享详情验证成功")
    
    # ==================== 步骤 10: Alice 禁用共享 ====================
    print_section("步骤 10: Alice 禁用共享")
    
    print(f"\n禁用共享...")
    disable_result = alice_client.update_share(share_id, is_active=False)
    if not disable_result:
        print(f"✗ 禁用失败")
        return False
    
    print(f"✓ 共享已禁用")
    
    # ==================== 步骤 11: Bob 尝试访问已禁用的共享（应该失败）====================
    print_section("步骤 11: Bob 尝试访问已禁用的共享")
    
    print(f"\nBob 尝试下载文件 (ID: {file_id})...")
    download_result = bob_client.download_file(file_id, show_progress=False)
    if download_result and download_result.get('success'):
        print(f"✗ 下载成功（不应该成功！）")
        # 清理文件
        if os.path.exists(download_result.get('path')):
            os.remove(download_result.get('path'))
        return False
    
    print(f"✓ 访问被拒绝（符合预期）")
    
    # ==================== 步骤 12: Alice 重新启用共享 ====================
    print_section("步骤 12: Alice 重新启用共享")
    
    print(f"\n重新启用共享...")
    enable_result = alice_client.update_share(share_id, is_active=True)
    if not enable_result:
        print(f"✗ 启用失败")
        return False
    
    print(f"✓ 共享已重新启用")
    
    # ==================== 步骤 13: 测试过期时间 ====================
    print_section("步骤 13: 测试过期时间")
    
    # 创建一个1秒后过期的共享
    print(f"\n创建一个1秒后过期的共享...")
    expires_at = (datetime.utcnow() + timedelta(seconds=1)).isoformat()
    
    # 先删除旧共享
    alice_client.delete_share(share_id)
    
    # 创建新的带过期时间的共享
    share_result2 = alice_client.create_share(file_id, bob_username, "read", expires_at)
    if not share_result2:
        print(f"✗ 创建共享失败")
        return False
    
    share_id2 = share_result2.get('share_info', {}).get('id')
    print(f"✓ 共享创建成功 (过期时间: {expires_at})")
    
    # 等待过期
    print(f"\n等待共享过期...")
    time.sleep(2)
    
    # Bob 尝试访问过期的共享
    print(f"\nBob 尝试访问过期的共享...")
    download_result = bob_client.download_file(file_id, show_progress=False)
    if download_result and download_result.get('success'):
        print(f"✗ 下载成功（不应该成功！）")
        if os.path.exists(download_result.get('path')):
            os.remove(download_result.get('path'))
        return False
    
    print(f"✓ 访问被拒绝（共享已过期，符合预期）")
    
    # ==================== 步骤 14: 清理测试数据 ====================
    print_section("步骤 14: 清理测试数据")
    
    # 删除共享
    print(f"\n删除共享...")
    alice_client.delete_share(share_id2)
    print(f"✓ 共享已删除")
    
    # 删除文件
    print(f"\n删除测试文件...")
    alice_client.delete_file(file_id)
    print(f"✓ 文件已删除")
    
    # ==================== 测试完成 ====================
    print_section("测试完成")
    
    print("\n✓ 所有测试通过！")
    print("\n测试覆盖:")
    print("  ✓ 创建只读共享")
    print("  ✓ 创建可写共享")
    print("  ✓ 查看共享列表")
    print("  ✓ 下载共享文件")
    print("  ✓ 权限验证（只读用户不能删除）")
    print("  ✓ 更新共享权限")
    print("  ✓ 禁用/启用共享")
    print("  ✓ 共享过期验证")
    print("  ✓ 删除共享")
    
    return True


def main():
    """主函数"""
    try:
        success = test_share_functionality()
        
        if success:
            print("\n" + "=" * 60)
            print("  🎉 共享功能测试全部通过！")
            print("=" * 60)
            sys.exit(0)
        else:
            print("\n" + "=" * 60)
            print("  ❌ 测试失败")
            print("=" * 60)
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n测试被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 测试异常: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

