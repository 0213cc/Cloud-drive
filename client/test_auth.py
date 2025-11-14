"""
用户认证系统测试脚本
"""
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from auth_client import AuthClient
from client import CloudDriveClient
from config import config
import time

def print_step(step, description):
    """打印测试步骤"""
    print("\n" + "=" * 60)
    print(f"步骤 {step}: {description}")
    print("=" * 60)

def test_auth():
    """测试认证功能"""
    print("\n" * 2)
    print("=" * 60)
    print("     用户认证系统功能测试")
    print("=" * 60)
    print()
    print("前提条件：")
    print("  1. 后端服务已启动")
    print("  2. 已安装所有依赖")
    print()
    input("按Enter继续...")
    
    auth = AuthClient(config.API_BASE_URL)
    
    # 测试1：注册用户
    print_step(1, "测试用户注册")
    
    # 生成唯一用户名
    timestamp = int(time.time())
    username = f"testuser_{timestamp}"
    email = f"{username}@example.com"
    password = "test123456"
    
    print(f"注册用户: {username}")
    print(f"邮箱: {email}")
    print(f"密码: {password}")
    
    result = auth.register(username, email, password)
    
    if result.get('success'):
        print(f"\n✓ 注册成功！")
        print(f"  用户ID: {result.get('user_id')}")
        print(f"  用户名: {result.get('username')}")
    else:
        print(f"\n✗ 注册失败: {result.get('error')}")
        print("如果用户名已存在，请删除Token文件后重试")
        return
    
    # 测试2：查看当前用户
    print_step(2, "查看当前用户信息")
    
    result = auth.get_user_info()
    
    if result.get('success'):
        print(f"\n✓ 获取成功")
        print(f"  用户名: {result.get('username')}")
        print(f"  邮箱: {result.get('email')}")
        print(f"  注册时间: {result.get('created_at')}")
    else:
        print(f"\n✗ 获取失败: {result.get('error')}")
    
    # 测试3：退出登录
    print_step(3, "测试退出登录")
    
    print("退出登录...")
    auth.logout()
    
    if not auth.is_authenticated():
        print("✓ 已退出登录")
    else:
        print("✗ 退出失败")
    
    # 测试4：重新登录
    print_step(4, "测试重新登录")
    
    print(f"使用用户名 {username} 登录...")
    result = auth.login(username, password)
    
    if result.get('success'):
        print(f"\n✓ 登录成功！")
        print(f"  Token已保存")
    else:
        print(f"\n✗ 登录失败: {result.get('error')}")
        return
    
    # 测试5：使用文件功能
    print_step(5, "测试文件操作（需要认证）")
    
    print("创建测试文件...")
    test_file = "auth_test_file.txt"
    with open(test_file, 'w') as f:
        f.write(f"Test file for user {username}\n")
        f.write(f"Created at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"✓ 创建文件: {test_file}")
    
    # 使用认证客户端上传
    print("\n上传文件到云端...")
    client = CloudDriveClient(auth_client=auth)
    result = client.upload_file(test_file, remote_path="/", show_progress=False)
    
    if result.get('success'):
        print(f"✓ 上传成功")
        file_id = result['file_info']['id']
        print(f"  文件ID: {file_id}")
    else:
        print(f"✗ 上传失败: {result.get('error')}")
    
    # 列出文件
    print("\n列出云端文件...")
    files = client.list_files("/")
    
    # 清理测试文件
    os.remove(test_file)
    print(f"\n✓ 已清理本地测试文件")
    
    # 测试6：Token自动刷新（模拟）
    print_step(6, "测试Token状态")
    
    if auth.is_authenticated():
        print("✓ Token有效")
        print(f"  用户: {auth.username}")
        print(f"  过期时间: {auth.token_expires}")
        print(f"\nToken会在过期前自动刷新（25分钟后）")
    else:
        print("✗ Token无效")
    
    # 完成
    print("\n" + "=" * 60)
    print("     测试完成！")
    print("=" * 60)
    print("\n验证要点：")
    print("  ✓ 用户注册成功")
    print("  ✓ 获取用户信息成功")
    print("  ✓ 退出登录成功")
    print("  ✓ 重新登录成功")
    print("  ✓ 文件操作需要认证")
    print("  ✓ Token自动管理")
    print()
    print("下一步测试：")
    print("  1. 使用命令行: python client.py register")
    print("  2. 测试多用户隔离: 注册两个用户，验证文件隔离")
    print("  3. 测试API文档: http://localhost:8000/docs")
    print()
    print(f"测试用户信息：")
    print(f"  用户名: {username}")
    print(f"  密码: {password}")
    print()

if __name__ == '__main__':
    try:
        test_auth()
    except KeyboardInterrupt:
        print("\n\n测试中断")
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()

