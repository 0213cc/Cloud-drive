"""
数据库迁移脚本 - 添加共享功能表

运行此脚本将在现有数据库中添加共享相关的表：
- shares: 文件共享表
- share_logs: 共享操作日志表
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, inspect
from app.models.database import Base, engine
from app.models.share import Share, ShareLog
from app.models.user import User
from app.models.file import File, FileHistory


def check_table_exists(table_name: str) -> bool:
    """检查表是否存在"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def migrate():
    """执行迁移"""
    print("=" * 60)
    print("数据库迁移 - 添加共享功能")
    print("=" * 60)
    
    # 检查现有表
    print("\n检查现有表...")
    existing_tables = inspect(engine).get_table_names()
    print(f"现有表: {', '.join(existing_tables)}")
    
    # 检查是否需要迁移
    needs_migration = False
    
    if not check_table_exists('shares'):
        print("\n✓ 需要创建 'shares' 表")
        needs_migration = True
    else:
        print("\n- 'shares' 表已存在")
    
    if not check_table_exists('share_logs'):
        print("✓ 需要创建 'share_logs' 表")
        needs_migration = True
    else:
        print("- 'share_logs' 表已存在")
    
    if not needs_migration:
        print("\n" + "=" * 60)
        print("数据库已是最新版本，无需迁移")
        print("=" * 60)
        return
    
    # 执行迁移
    print("\n开始迁移...")
    try:
        # 创建新表
        Base.metadata.create_all(bind=engine, checkfirst=True)
        
        print("\n✓ 迁移成功！")
        
        # 显示新表结构
        print("\n新增表结构:")
        
        if check_table_exists('shares'):
            print("\n1. shares (文件共享表):")
            inspector = inspect(engine)
            columns = inspector.get_columns('shares')
            for col in columns:
                print(f"   - {col['name']}: {col['type']}")
        
        if check_table_exists('share_logs'):
            print("\n2. share_logs (共享操作日志表):")
            inspector = inspect(engine)
            columns = inspector.get_columns('share_logs')
            for col in columns:
                print(f"   - {col['name']}: {col['type']}")
        
        print("\n" + "=" * 60)
        print("迁移完成！现在可以使用共享功能了")
        print("=" * 60)
        
        print("\n使用方法:")
        print("  1. 创建共享: python client.py share <file_id> <username>")
        print("  2. 查看我的共享: python client.py my-shares")
        print("  3. 查看分享给我的: python client.py shared-with-me")
        print("  4. 删除共享: python client.py unshare <share_id>")
        
    except Exception as e:
        print(f"\n✗ 迁移失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def rollback():
    """回滚迁移（删除共享表）"""
    print("=" * 60)
    print("回滚迁移 - 删除共享功能表")
    print("=" * 60)
    
    print("\n警告: 此操作将删除所有共享数据！")
    confirm = input("确定要继续吗? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("已取消")
        return
    
    try:
        from sqlalchemy import MetaData, Table
        
        metadata = MetaData()
        metadata.bind = engine
        
        # 删除表
        if check_table_exists('share_logs'):
            table = Table('share_logs', metadata, autoload=True)
            table.drop(engine)
            print("✓ 已删除 'share_logs' 表")
        
        if check_table_exists('shares'):
            table = Table('shares', metadata, autoload=True)
            table.drop(engine)
            print("✓ 已删除 'shares' 表")
        
        print("\n" + "=" * 60)
        print("回滚完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ 回滚失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='数据库迁移脚本 - 共享功能')
    parser.add_argument(
        'action',
        choices=['migrate', 'rollback'],
        default='migrate',
        nargs='?',
        help='操作: migrate (迁移) 或 rollback (回滚)'
    )
    
    args = parser.parse_args()
    
    if args.action == 'rollback':
        rollback()
    else:
        migrate()

