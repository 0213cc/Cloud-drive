"""
断点续传功能数据库迁移脚本

创建断点续传所需的数据表：
1. upload_sessions - 上传会话表
"""
import sqlite3
import sys
import os

# 添加app目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from config import get_settings

settings = get_settings()
DB_PATH = settings.database_url.replace('sqlite:///', '')


def check_table_exists(cursor, table_name):
    """检查表是否存在"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def migrate_database():
    """执行数据库迁移"""
    print(f"开始迁移数据库: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"✗ 数据库文件不存在: {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. 创建 upload_sessions 表
        if not check_table_exists(cursor, 'upload_sessions'):
            print("创建 upload_sessions 表...")
            cursor.execute("""
                CREATE TABLE upload_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    upload_id VARCHAR(128) NOT NULL UNIQUE,
                    user_id INTEGER NOT NULL,
                    file_hash VARCHAR(64) NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    path VARCHAR(500) NOT NULL,
                    total_size BIGINT NOT NULL,
                    chunk_size INTEGER NOT NULL,
                    total_chunks INTEGER NOT NULL,
                    uploaded_chunks TEXT,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)

            # 创建索引
            cursor.execute(
                "CREATE INDEX idx_upload_sessions_upload_id ON upload_sessions(upload_id)"
            )
            cursor.execute(
                "CREATE INDEX idx_upload_sessions_user_file ON upload_sessions(user_id, file_hash)"
            )

            print("✓ upload_sessions 表创建成功")
        else:
            print("✓ upload_sessions 表已存在")

        # 提交更改
        conn.commit()

        print("\n✓ 数据库迁移成功！")
        print("\n断点续传功能的数据表已准备就绪。")

        return True

    except Exception as e:
        print(f"\n✗ 数据库迁移失败: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 80)
    print("断点续传数据库迁移")
    print("=" * 80)
    print()

    success = migrate_database()

    if success:
        print("\n" + "=" * 80)
        print("下一步:")
        print("=" * 80)
        print("1. 重启后端服务")
        print("2. 开始使用断点续传功能")
        print()
    else:
        print("\n迁移失败，请检查错误信息并重试。")
        sys.exit(1)

