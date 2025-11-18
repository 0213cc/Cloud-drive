"""
修复文件块引用计数
检查并修复file_chunks表中的reference_count字段
"""
import sqlite3
import sys
import os


def fix_reference_counts(db_path='cloud_drive.db'):
    """
    修复文件块的引用计数
    
    Args:
        db_path: 数据库文件路径
    """
    print(f"开始修复引用计数: {db_path}\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. 获取所有文件块及其实际引用次数
        print("分析文件块引用情况...")
        
        cursor.execute("""
            SELECT 
                fc.id,
                fc.hash_value,
                fc.reference_count as stored_count,
                COUNT(f.id) as actual_count_files,
                COUNT(fh.id) as actual_count_history
            FROM file_chunks fc
            LEFT JOIN files f ON f.chunk_id = fc.id
            LEFT JOIN file_history fh ON fh.chunk_id = fc.id
            GROUP BY fc.id
        """)
        
        chunks = cursor.fetchall()
        
        print(f"找到 {len(chunks)} 个文件块\n")
        
        # 2. 检查不一致的引用计数
        inconsistent = []
        
        for chunk_id, hash_value, stored_count, actual_files, actual_history in chunks:
            actual_total = actual_files + actual_history
            
            if stored_count != actual_total:
                inconsistent.append({
                    'id': chunk_id,
                    'hash': hash_value[:16] + '...',
                    'stored': stored_count,
                    'actual': actual_total,
                    'files': actual_files,
                    'history': actual_history
                })
        
        if not inconsistent:
            print("✓ 所有文件块的引用计数都正确！")
            return
        
        print(f"发现 {len(inconsistent)} 个文件块的引用计数不一致:\n")
        
        print(f"{'Chunk ID':<10} {'Hash':<20} {'存储计数':<10} {'实际计数':<10} {'文件':<8} {'历史':<8}")
        print("-" * 80)
        
        for item in inconsistent:
            print(f"{item['id']:<10} {item['hash']:<20} {item['stored']:<10} "
                  f"{item['actual']:<10} {item['files']:<8} {item['history']:<8}")
        
        # 3. 询问是否修复
        print(f"\n是否修复这些引用计数? (y/n): ", end="")
        response = input().strip().lower()
        
        if response != 'y':
            print("取消修复")
            return
        
        # 4. 修复引用计数
        print("\n开始修复...")
        
        fixed = 0
        deleted = 0
        
        for item in inconsistent:
            chunk_id = item['id']
            actual_count = item['actual']
            
            if actual_count == 0:
                # 没有引用，删除文件块
                print(f"  删除无引用的文件块: chunk_id={chunk_id}")
                
                cursor.execute("DELETE FROM file_chunks WHERE id = ?", (chunk_id,))
                deleted += 1
            else:
                # 更新引用计数
                print(f"  更新引用计数: chunk_id={chunk_id}, {item['stored']} -> {actual_count}")
                
                cursor.execute("""
                    UPDATE file_chunks 
                    SET reference_count = ?
                    WHERE id = ?
                """, (actual_count, chunk_id))
                fixed += 1
        
        # 提交更改
        conn.commit()
        
        print(f"\n✓ 修复完成!")
        print(f"  更新: {fixed} 个文件块")
        print(f"  删除: {deleted} 个文件块")
        
        # 5. 验证修复结果
        print("\n验证修复结果...")
        
        cursor.execute("""
            SELECT 
                fc.id,
                fc.reference_count,
                COUNT(f.id) + COUNT(fh.id) as actual_count
            FROM file_chunks fc
            LEFT JOIN files f ON f.chunk_id = fc.id
            LEFT JOIN file_history fh ON fh.chunk_id = fc.id
            GROUP BY fc.id
            HAVING fc.reference_count != actual_count
        """)
        
        remaining = cursor.fetchall()
        
        if remaining:
            print(f"  ⚠️  仍有 {len(remaining)} 个文件块的引用计数不一致")
        else:
            print("  ✓ 所有文件块的引用计数已正确")
        
    except Exception as e:
        print(f"\n✗ 修复失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def show_statistics(db_path='cloud_drive.db'):
    """
    显示去重统计信息
    
    Args:
        db_path: 数据库文件路径
    """
    print(f"\n{'=' * 80}")
    print("去重统计信息")
    print('=' * 80)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 总文件块数
        cursor.execute("SELECT COUNT(*) FROM file_chunks")
        total_chunks = cursor.fetchone()[0]
        
        # 被去重的文件块数
        cursor.execute("SELECT COUNT(*) FROM file_chunks WHERE reference_count > 1")
        dedup_chunks = cursor.fetchone()[0]
        
        # 总引用次数
        cursor.execute("SELECT SUM(reference_count) FROM file_chunks")
        total_refs = cursor.fetchone()[0] or 0
        
        # 节省的副本数
        cursor.execute("SELECT SUM(reference_count - 1) FROM file_chunks WHERE reference_count > 1")
        saved_copies = cursor.fetchone()[0] or 0
        
        # 节省的空间
        cursor.execute("""
            SELECT SUM(size * (reference_count - 1)) 
            FROM file_chunks 
            WHERE reference_count > 1
        """)
        saved_bytes = cursor.fetchone()[0] or 0
        
        # 实际存储空间
        cursor.execute("SELECT SUM(COALESCE(compressed_size, size)) FROM file_chunks")
        actual_storage = cursor.fetchone()[0] or 0
        
        # 无去重时需要的空间
        cursor.execute("SELECT SUM(size * reference_count) FROM file_chunks")
        total_without_dedup = cursor.fetchone()[0] or 0
        
        print(f"\n文件块统计:")
        print(f"  总文件块数: {total_chunks}")
        print(f"  被去重的文件块数: {dedup_chunks}")
        print(f"  总引用次数: {total_refs}")
        print(f"  节省的副本数: {saved_copies}")
        
        print(f"\n存储空间:")
        print(f"  实际存储: {actual_storage / 1024 / 1024:.2f} MB")
        print(f"  无去重时需要: {total_without_dedup / 1024 / 1024:.2f} MB")
        print(f"  节省空间: {saved_bytes / 1024 / 1024:.2f} MB")
        
        if total_without_dedup > 0:
            dedup_ratio = (saved_bytes / total_without_dedup) * 100
            print(f"  去重率: {dedup_ratio:.2f}%")
        
        # 引用次数最多的文件块
        print(f"\n引用次数最多的文件块:")
        cursor.execute("""
            SELECT 
                hash_value,
                size / 1024 / 1024 as size_mb,
                reference_count,
                is_compressed
            FROM file_chunks
            ORDER BY reference_count DESC
            LIMIT 5
        """)
        
        print(f"  {'Hash':<20} {'大小(MB)':<12} {'引用次数':<10} {'压缩':<6}")
        print("  " + "-" * 60)
        
        for hash_val, size_mb, refs, compressed in cursor.fetchall():
            hash_short = hash_val[:16] + '...'
            compressed_str = '是' if compressed else '否'
            print(f"  {hash_short:<20} {size_mb:<12.2f} {refs:<10} {compressed_str:<6}")
        
    finally:
        conn.close()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='修复文件块引用计数')
    parser.add_argument(
        '--db',
        default='cloud_drive.db',
        help='数据库文件路径（默认: cloud_drive.db）'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='只显示统计信息，不修复'
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.db):
        print(f"错误：数据库文件不存在: {args.db}")
        print("请确保在backend目录下运行此脚本")
        sys.exit(1)
    
    try:
        if args.stats:
            show_statistics(args.db)
        else:
            fix_reference_counts(args.db)
            show_statistics(args.db)
    except Exception as e:
        print(f"\n操作失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

