"""
数据库迁移脚本 - 文件去重功能
确保file_chunks表存在并且files表有chunk_id字段
"""
import sqlite3
import sys
import os

# 添加app目录到路径
sys.path.insert(0, os.path.dirname(__file__))

def migrate_database(db_path='cloud_drive.db'):
    """
    迁移数据库以支持文件去重
    
    Args:
        db_path: 数据库文件路径
    """
    print(f"开始迁移数据库: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. 检查file_chunks表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='file_chunks'
        """)
        
        if not cursor.fetchone():
            print("创建file_chunks表...")
            cursor.execute("""
                CREATE TABLE file_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash_value VARCHAR(64) NOT NULL UNIQUE,
                    size BIGINT NOT NULL,
                    is_compressed BOOLEAN DEFAULT 0,
                    compressed_size BIGINT,
                    compression_ratio INTEGER,
                    s3_key VARCHAR(500) NOT NULL UNIQUE,
                    s3_etag VARCHAR(100),
                    stored_content_type VARCHAR(100),
                    reference_count INTEGER DEFAULT 1 NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX ix_file_chunks_hash_value ON file_chunks(hash_value)
            """)
            
            print("✓ file_chunks表创建完成")
        else:
            print("✓ file_chunks表已存在")
        
        # 2. 检查files表是否有chunk_id字段
        cursor.execute("PRAGMA table_info(files)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'chunk_id' not in columns:
            print("添加chunk_id字段到files表...")
            cursor.execute("""
                ALTER TABLE files ADD COLUMN chunk_id INTEGER
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX ix_files_chunk_id ON files(chunk_id)
            """)
            
            print("✓ files表添加chunk_id字段完成")
        else:
            print("✓ files表已有chunk_id字段")
        
        # 3. 检查file_history表是否有chunk_id字段
        cursor.execute("PRAGMA table_info(file_history)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'chunk_id' not in columns:
            print("添加chunk_id字段到file_history表...")
            cursor.execute("""
                ALTER TABLE file_history ADD COLUMN chunk_id INTEGER
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX ix_file_history_chunk_id ON file_history(chunk_id)
            """)
            
            print("✓ file_history表添加chunk_id字段完成")
        else:
            print("✓ file_history表已有chunk_id字段")
        
        # 4. 迁移现有数据（如果需要）
        print("\n检查是否需要迁移现有数据...")
        
        # 查找没有chunk_id的文件
        cursor.execute("""
            SELECT COUNT(*) FROM files 
            WHERE chunk_id IS NULL AND is_directory = 0
        """)
        files_without_chunk = cursor.fetchone()[0]
        
        if files_without_chunk > 0:
            print(f"发现 {files_without_chunk} 个文件没有chunk_id，开始迁移...")
            
            # 获取所有没有chunk_id的文件
            cursor.execute("""
                SELECT id, hash_value, size, s3_key, s3_etag, 
                       is_compressed, compressed_size, compression_ratio
                FROM files 
                WHERE chunk_id IS NULL AND is_directory = 0
            """)
            
            files = cursor.fetchall()
            migrated = 0
            
            for file_data in files:
                file_id, hash_value, size, s3_key, s3_etag, is_compressed, compressed_size, compression_ratio = file_data
                
                if not hash_value or not s3_key:
                    continue
                
                # 检查是否已有相同哈希的chunk
                cursor.execute("""
                    SELECT id FROM file_chunks WHERE hash_value = ?
                """, (hash_value,))
                
                existing_chunk = cursor.fetchone()
                
                if existing_chunk:
                    # 使用已存在的chunk
                    chunk_id = existing_chunk[0]
                    
                    # 增加引用计数
                    cursor.execute("""
                        UPDATE file_chunks 
                        SET reference_count = reference_count + 1
                        WHERE id = ?
                    """, (chunk_id,))
                else:
                    # 创建新的chunk
                    cursor.execute("""
                        INSERT INTO file_chunks 
                        (hash_value, size, s3_key, s3_etag, is_compressed, 
                         compressed_size, compression_ratio, reference_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """, (hash_value, size, s3_key, s3_etag, is_compressed, 
                          compressed_size, compression_ratio))
                    
                    chunk_id = cursor.lastrowid
                
                # 更新文件记录
                cursor.execute("""
                    UPDATE files SET chunk_id = ? WHERE id = ?
                """, (chunk_id, file_id))
                
                migrated += 1
                
                if migrated % 100 == 0:
                    print(f"  已迁移 {migrated}/{files_without_chunk} 个文件...")
            
            print(f"✓ 迁移完成，共迁移 {migrated} 个文件")
        else:
            print("✓ 所有文件都已有chunk_id，无需迁移")
        
        # 提交更改
        conn.commit()
        
        # 5. 验证迁移结果
        print("\n验证迁移结果...")
        
        cursor.execute("SELECT COUNT(*) FROM file_chunks")
        chunk_count = cursor.fetchone()[0]
        print(f"  文件块总数: {chunk_count}")
        
        cursor.execute("""
            SELECT COUNT(*) FROM files 
            WHERE chunk_id IS NOT NULL AND is_directory = 0
        """)
        files_with_chunk = cursor.fetchone()[0]
        print(f"  关联文件块的文件数: {files_with_chunk}")
        
        cursor.execute("""
            SELECT SUM(reference_count) FROM file_chunks
        """)
        total_refs = cursor.fetchone()[0] or 0
        print(f"  总引用次数: {total_refs}")
        
        if total_refs != files_with_chunk:
            print(f"  ⚠️  警告：引用计数({total_refs})与文件数({files_with_chunk})不匹配")
            print("  可能需要运行: python fix_reference_counts.py")
        
        print("\n✓ 数据库迁移成功！")
        print("现在可以使用文件去重功能了")
        
    except Exception as e:
        print(f"\n✗ 迁移失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='迁移数据库以支持文件去重')
    parser.add_argument(
        '--db',
        default='cloud_drive.db',
        help='数据库文件路径（默认: cloud_drive.db）'
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.db):
        print(f"错误：数据库文件不存在: {args.db}")
        print("请确保在backend目录下运行此脚本")
        sys.exit(1)
    
    try:
        migrate_database(args.db)
    except Exception as e:
        print(f"\n迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
