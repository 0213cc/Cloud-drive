import sqlite3
import os

# 确保脚本在 backend 目录下运行
DB_PATH = os.path.join(os.path.dirname(__file__), 'cloud_drive.db')

def migrate():
    """运行数据库迁移"""
    if not os.path.exists(DB_PATH):
        print(f"错误：数据库文件不存在于 {DB_PATH}")
        print("请确认文件名是否为 cloud_drive.db 并且该脚本在 backend 目录下运行。")
        return

    print(f"连接到数据库: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. 为 files 表添加 version 列
        print("检查 'files' 表...")
        cursor.execute("PRAGMA table_info(files)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'version' not in columns:
            print("  -> 正在添加 'version' 列到 'files' 表...")
            cursor.execute("ALTER TABLE files ADD COLUMN version INTEGER NOT NULL DEFAULT 1;")
            print("  ✓ 'version' 列添加成功。")
        else:
            print("  - 'version' 列已存在，跳过。")

        # 2. 创建 file_history 表
        print("\n检查 'file_history' 表...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_history (
                id INTEGER NOT NULL, 
                file_id INTEGER NOT NULL, 
                version INTEGER NOT NULL, 
                size BIGINT NOT NULL, 
                hash_value VARCHAR(64), 
                s3_key VARCHAR(500) NOT NULL, 
                s3_etag VARCHAR(100), 
                created_at DATETIME, 
                PRIMARY KEY (id), 
                FOREIGN KEY(file_id) REFERENCES files (id)
            );
        """)
        print("  ✓ 'file_history' 表已创建或已存在。")
        
        # 为 file_history 表创建索引
        print("  -> 正在创建索引...")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_file_history_file_id ON file_history (file_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_file_history_id ON file_history (id);")
        print("  ✓ 索引创建成功。")

        conn.commit()
        print("\n数据库迁移成功！")

    except Exception as e:
        print(f"\n数据库迁移过程中发生错误: {e}")
        conn.rollback()
    finally:
        conn.close()
        print("数据库连接已关闭。")

if __name__ == "__main__":
    migrate()
