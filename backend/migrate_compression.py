"""
数据库迁移脚本 - 添加压缩功能相关字段
"""
import sqlite3
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from config import get_settings

settings = get_settings()


def migrate_database():
    """添加压缩相关字段到现有数据库"""
    db_path = "cloud_drive.db"
    
    if not os.path.exists(db_path):
        print("数据库文件不存在，无需迁移")
        return
    
    print(f"开始迁移数据库: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查files表的字段
        cursor.execute("PRAGMA table_info(files)")
        columns = [col[1] for col in cursor.fetchall()]
        
        print("检查files表...")
        fields_added = 0
        
        # 逐个检查并添加缺失的字段
        if 'is_compressed' not in columns:
            cursor.execute("""
                ALTER TABLE files ADD COLUMN is_compressed BOOLEAN DEFAULT 0
            """)
            print("  ✓ 添加字段: is_compressed")
            fields_added += 1
        else:
            print("  - is_compressed 已存在")
        
        if 'compressed_size' not in columns:
            cursor.execute("""
                ALTER TABLE files ADD COLUMN compressed_size BIGINT
            """)
            print("  ✓ 添加字段: compressed_size")
            fields_added += 1
        else:
            print("  - compressed_size 已存在")
        
        if 'compression_ratio' not in columns:
            cursor.execute("""
                ALTER TABLE files ADD COLUMN compression_ratio INTEGER
            """)
            print("  ✓ 添加字段: compression_ratio")
            fields_added += 1
        else:
            print("  - compression_ratio 已存在")
        
        if fields_added > 0:
            print(f"✓ files表添加了 {fields_added} 个字段")
        else:
            print("✓ files表所有字段已存在")
        
        # 检查file_history表
        cursor.execute("PRAGMA table_info(file_history)")
        columns = [col[1] for col in cursor.fetchall()]
        
        print("\n检查file_history表...")
        fields_added = 0
        
        if 'is_compressed' not in columns:
            cursor.execute("""
                ALTER TABLE file_history ADD COLUMN is_compressed BOOLEAN DEFAULT 0
            """)
            print("  ✓ 添加字段: is_compressed")
            fields_added += 1
        else:
            print("  - is_compressed 已存在")
        
        if 'compressed_size' not in columns:
            cursor.execute("""
                ALTER TABLE file_history ADD COLUMN compressed_size BIGINT
            """)
            print("  ✓ 添加字段: compressed_size")
            fields_added += 1
        else:
            print("  - compressed_size 已存在")
        
        if fields_added > 0:
            print(f"✓ file_history表添加了 {fields_added} 个字段")
        else:
            print("✓ file_history表所有字段已存在")
        
        conn.commit()
        print("\n✓ 数据库迁移成功！")
        print("现在可以使用压缩功能了")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ 迁移失败: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()

