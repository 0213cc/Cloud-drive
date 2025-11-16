"""
文件版本控制测试脚本
"""
import requests
import json
import os
from pathlib import Path

# 配置
BASE_URL = "http://localhost:8000"
USERNAME = "testuser"
PASSWORD = "testpass123"

class VersionControlTester:
    def __init__(self):
        self.token = None
        self.headers = {}
        
    def login(self):
        """登录获取token"""
        print("\n=== 1. 登录 ===")
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": USERNAME, "password": PASSWORD}
        )
        
        if response.status_code == 200:
            data = response.json()
            self.token = data['access_token']
            self.headers = {"Authorization": f"Bearer {self.token}"}
            print(f"✓ 登录成功，Token: {self.token[:20]}...")
            return True
        else:
            print(f"✗ 登录失败: {response.text}")
            return False
    
    def register(self):
        """注册新用户"""
        print("\n=== 注册新用户 ===")
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "username": USERNAME,
                "email": f"{USERNAME}@example.com",
                "password": PASSWORD
            }
        )
        
        if response.status_code == 200:
            print(f"✓ 注册成功")
            return True
        elif response.status_code == 400:
            print(f"用户已存在，尝试登录...")
            return False
        else:
            print(f"✗ 注册失败: {response.text}")
            return False
    
    def create_test_file(self, filename, content):
        """创建测试文件"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ 创建测试文件: {filename}")
    
    def upload_file(self, filepath, remote_path="/"):
        """上传文件"""
        print(f"\n=== 上传文件: {filepath} ===")
        
        with open(filepath, 'rb') as f:
            files = {'file': (os.path.basename(filepath), f)}
            response = requests.post(
                f"{BASE_URL}/api/files/upload",
                files=files,
                params={"path": remote_path},
                headers=self.headers
            )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 上传成功")
            print(f"  文件ID: {data['file_info']['id']}")
            print(f"  版本: {data['file_info']['version']}")
            print(f"  大小: {data['file_info']['size']} bytes")
            print(f"  哈希: {data['file_info']['hash_value']}")
            return data['file_info']['id']
        else:
            print(f"✗ 上传失败: {response.text}")
            return None
    
    def get_file_info(self, file_id):
        """获取文件信息"""
        print(f"\n=== 获取文件信息: ID={file_id} ===")
        response = requests.get(
            f"{BASE_URL}/api/files/info/{file_id}",
            headers=self.headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 文件信息:")
            print(f"  路径: {data['path']}")
            print(f"  文件名: {data['filename']}")
            print(f"  当前版本: {data['version']}")
            print(f"  大小: {data['size']} bytes")
            print(f"  哈希: {data['hash_value']}")
            print(f"  更新时间: {data['updated_at']}")
            return data
        else:
            print(f"✗ 获取失败: {response.text}")
            return None
    
    def get_file_history(self, file_id):
        """获取文件历史版本"""
        print(f"\n=== 获取文件历史版本: ID={file_id} ===")
        response = requests.get(
            f"{BASE_URL}/api/files/history/{file_id}",
            headers=self.headers
        )
        
        if response.status_code == 200:
            history = response.json()
            if history:
                print(f"✓ 找到 {len(history)} 个历史版本:")
                for h in history:
                    print(f"  版本 {h['version']}: {h['size']} bytes, 哈希={h['hash_value'][:16]}..., 创建于 {h['created_at']}")
            else:
                print("  暂无历史版本")
            return history
        else:
            print(f"✗ 获取失败: {response.text}")
            return None
    
    def revert_file(self, file_id, version):
        """回滚文件到指定版本"""
        print(f"\n=== 回滚文件到版本 {version}: ID={file_id} ===")
        response = requests.post(
            f"{BASE_URL}/api/files/revert/{file_id}",
            params={"version": version},
            headers=self.headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ {data['message']}")
            print(f"  新版本号: {data['file_info']['version']}")
            print(f"  大小: {data['file_info']['size']} bytes")
            print(f"  哈希: {data['file_info']['hash_value']}")
            return True
        else:
            print(f"✗ 回滚失败: {response.text}")
            return False
    
    def download_file(self, file_id, save_path):
        """下载文件"""
        print(f"\n=== 下载文件: ID={file_id} ===")
        response = requests.get(
            f"{BASE_URL}/api/files/download/{file_id}",
            headers=self.headers
        )
        
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            print(f"✓ 下载成功，保存到: {save_path}")
            
            # 显示文件内容（如果是文本文件）
            try:
                with open(save_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(f"  文件内容:\n{content}")
            except:
                print(f"  (二进制文件，无法显示内容)")
            return True
        else:
            print(f"✗ 下载失败: {response.text}")
            return False
    
    def run_test(self):
        """运行完整测试"""
        print("=" * 60)
        print("文件版本控制功能测试")
        print("=" * 60)
        
        # 1. 注册/登录
        if not self.register():
            if not self.login():
                return
        else:
            self.login()
        
        # 2. 创建测试文件
        test_file = "test_version.txt"
        
        # 3. 第一次上传（版本1）
        print("\n" + "=" * 60)
        print("测试场景 1: 上传文件的第一个版本")
        print("=" * 60)
        self.create_test_file(test_file, "这是版本1的内容\n第一次上传")
        file_id = self.upload_file(test_file)
        
        if not file_id:
            print("测试失败：无法上传文件")
            return
        
        # 4. 查看文件信息
        self.get_file_info(file_id)
        
        # 5. 第二次上传（版本2）
        print("\n" + "=" * 60)
        print("测试场景 2: 上传文件的第二个版本")
        print("=" * 60)
        self.create_test_file(test_file, "这是版本2的内容\n第二次上传，内容已修改")
        self.upload_file(test_file)
        self.get_file_info(file_id)
        
        # 6. 第三次上传（版本3）
        print("\n" + "=" * 60)
        print("测试场景 3: 上传文件的第三个版本")
        print("=" * 60)
        self.create_test_file(test_file, "这是版本3的内容\n第三次上传，内容再次修改\n增加了更多行")
        self.upload_file(test_file)
        self.get_file_info(file_id)
        
        # 7. 查看历史版本
        print("\n" + "=" * 60)
        print("测试场景 4: 查看文件历史版本")
        print("=" * 60)
        history = self.get_file_history(file_id)
        
        # 8. 回滚到版本1
        if history and len(history) >= 2:
            print("\n" + "=" * 60)
            print("测试场景 5: 回滚到版本1")
            print("=" * 60)
            self.revert_file(file_id, 1)
            self.get_file_info(file_id)
            
            # 下载并查看内容
            self.download_file(file_id, "downloaded_version1.txt")
            
            # 9. 再次查看历史版本
            print("\n" + "=" * 60)
            print("测试场景 6: 回滚后再次查看历史版本")
            print("=" * 60)
            self.get_file_history(file_id)
        
        # 10. 清理测试文件
        print("\n" + "=" * 60)
        print("清理测试文件")
        print("=" * 60)
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"✓ 删除: {test_file}")
        if os.path.exists("downloaded_version1.txt"):
            os.remove("downloaded_version1.txt")
            print(f"✓ 删除: downloaded_version1.txt")
        
        print("\n" + "=" * 60)
        print("测试完成！")
        print("=" * 60)


def main():
    """主函数"""
    tester = VersionControlTester()
    
    print("\n请选择测试模式:")
    print("1. 自动测试（运行完整测试流程）")
    print("2. 手动测试（交互式）")
    
    choice = input("\n请输入选项 (1/2): ").strip()
    
    if choice == "1":
        tester.run_test()
    elif choice == "2":
        # 手动测试模式
        if not tester.register():
            if not tester.login():
                return
        else:
            tester.login()
        
        while True:
            print("\n" + "=" * 60)
            print("手动测试菜单")
            print("=" * 60)
            print("1. 上传文件")
            print("2. 获取文件信息")
            print("3. 查看文件历史版本")
            print("4. 回滚文件")
            print("5. 下载文件")
            print("0. 退出")
            
            cmd = input("\n请输入命令: ").strip()
            
            if cmd == "1":
                filepath = input("请输入文件路径: ").strip()
                if os.path.exists(filepath):
                    tester.upload_file(filepath)
                else:
                    print(f"文件不存在: {filepath}")
            
            elif cmd == "2":
                file_id = input("请输入文件ID: ").strip()
                if file_id.isdigit():
                    tester.get_file_info(int(file_id))
            
            elif cmd == "3":
                file_id = input("请输入文件ID: ").strip()
                if file_id.isdigit():
                    tester.get_file_history(int(file_id))
            
            elif cmd == "4":
                file_id = input("请输入文件ID: ").strip()
                version = input("请输入要回滚到的版本号: ").strip()
                if file_id.isdigit() and version.isdigit():
                    tester.revert_file(int(file_id), int(version))
            
            elif cmd == "5":
                file_id = input("请输入文件ID: ").strip()
                save_path = input("请输入保存路径: ").strip()
                if file_id.isdigit():
                    tester.download_file(int(file_id), save_path)
            
            elif cmd == "0":
                print("退出测试")
                break
            
            else:
                print("无效的命令")
    else:
        print("无效的选项")


if __name__ == "__main__":
    main()

