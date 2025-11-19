"""
块级去重数据库迁移脚本

创建块级去重所需的数据表：
1. block_chunks - 数据块表
2. file_block_maps - 文件-数据块映射表
3. file_block_metadata - 文件块元数据表
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
        # 1. 创建 block_chunks 表
        if not check_table_exists(cursor, 'block_chunks'):
            print("创建 block_chunks 表...")
            cursor.execute("""
                CREATE TABLE block_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash_value VARCHAR(64) NOT NULL UNIQUE,
                    size BIGINT NOT NULL,
                    is_compressed BOOLEAN DEFAULT 0,
                    compressed_size BIGINT,
                    compression_ratio INTEGER,
                    s3_key VARCHAR(500) NOT NULL UNIQUE,
                    s3_etag VARCHAR(100),
                    stored_content_type VARCHAR(100),
                    reference_count INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            cursor.execute(
                "CREATE INDEX idx_block_chunks_hash ON block_chunks(hash_value)"
            )
            cursor.execute(
                "CREATE INDEX idx_block_chunks_s3_key ON block_chunks(s3_key)"
            )
            
            print("✓ block_chunks 表创建成功")
        else:
            print("✓ block_chunks 表已存在")
        
        # 2. 创建 file_block_maps 表
        if not check_table_exists(cursor, 'file_block_maps'):
            print("创建 file_block_maps 表...")
            cursor.execute("""
                CREATE TABLE file_block_maps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_chunk_id INTEGER NOT NULL,
                    block_chunk_id INTEGER NOT NULL,
                    block_index INTEGER NOT NULL,
                    block_offset BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_chunk_id) REFERENCES file_chunks(id),
                    FOREIGN KEY (block_chunk_id) REFERENCES block_chunks(id)
                )
            """)
            
            # 创建索引
            cursor.execute(
                "CREATE INDEX idx_file_block_maps_file_chunk ON file_block_maps(file_chunk_id)"
            )
            cursor.execute(
                "CREATE INDEX idx_file_block_maps_block_chunk ON file_block_maps(block_chunk_id)"
            )
            cursor.execute(
                "CREATE INDEX idx_file_block_maps_file_block_index ON file_block_maps(file_chunk_id, block_index)"
            )
            
            print("✓ file_block_maps 表创建成功")
        else:
            print("✓ file_block_maps 表已存在")
        
        # 3. 创建 file_block_metadata 表
        if not check_table_exists(cursor, 'file_block_metadata'):
            print("创建 file_block_metadata 表...")
            cursor.execute("""
                CREATE TABLE file_block_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_chunk_id INTEGER NOT NULL UNIQUE,
                    chunking_algorithm VARCHAR(50) NOT NULL,
                    chunk_size INTEGER NOT NULL,
                    total_blocks INTEGER NOT NULL,
                    unique_blocks INTEGER NOT NULL,
                    deduplication_ratio INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_chunk_id) REFERENCES file_chunks(id)
                )
            """)
            
            # 创建索引
            cursor.execute(
                "CREATE INDEX idx_file_block_metadata_file_chunk ON file_block_metadata(file_chunk_id)"
            )
            
            print("✓ file_block_metadata 表创建成功")
        else:
            print("✓ file_block_metadata 表已存在")
        
        # 提交更改
        conn.commit()
        
        print("\n✓ 数据库迁移成功！")
        print("\n块级去重功能已启用，可以开始使用。")
        
        return True
    
    except Exception as e:
        print(f"\n✗ 数据库迁移失败: {e}")
        conn.rollback()
        return False
    
    finally:
        conn.close()


def verify_migration():
    """验证迁移结果"""
    print("\n" + "=" * 80)
    print("验证迁移结果")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 检查表
        tables = ['block_chunks', 'file_block_maps', 'file_block_metadata']
        
        for table in tables:
            if check_table_exists(cursor, table):
                # 获取表结构
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                
                print(f"\n✓ {table} 表:")
                print(f"  列数: {len(columns)}")
                
                # 获取记录数
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  记录数: {count}")
            else:
                print(f"\n✗ {table} 表不存在")
        
        print("\n" + "=" * 80)
    
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 80)
    print("块级去重数据库迁移")
    print("=" * 80)
    print()
    
    success = migrate_database()
    
    if success:
        verify_migration()
        
        print("\n" + "=" * 80)
        print("下一步:")
        print("=" * 80)
        print("1. 重启后端服务")
        print("2. 运行测试脚本: python test_block_deduplication.py")
        print("3. 开始使用块级去重功能上传大文件")
        print()
    else:
        print("\n迁移失败，请检查错误信息并重试。")
        sys.exit(1)

