"""
检查并修复数据库结构
"""
import sqlite3
import os

def check_and_fix_database():
    """检查并修复数据库结构"""
    db_path = "cloud_drive.db"
    
    if not os.path.exists(db_path):
        print("❌ 数据库文件不存在")
        return
    
    print(f"检查数据库: {db_path}\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查files表
        print("=" * 60)
        print("检查 files 表")
        print("=" * 60)
        cursor.execute("PRAGMA table_info(files)")
        columns = {col[1]: col[2] for col in cursor.fetchall()}
        
        print(f"当前字段数: {len(columns)}")
        for col_name, col_type in columns.items():
            print(f"  ✓ {col_name} ({col_type})")
        
        # 需要添加的字段
        missing_fields = []
        
        if 'compressed_size' not in columns:
            missing_fields.append(('compressed_size', 'BIGINT'))
            
        if 'compression_ratio' not in columns:
            missing_fields.append(('compression_ratio', 'INTEGER'))
        
        if missing_fields:
            print(f"\n⚠️  缺少 {len(missing_fields)} 个字段，开始添加...")
            for field_name, field_type in missing_fields:
                try:
                    cursor.execute(f"""
                        ALTER TABLE files ADD COLUMN {field_name} {field_type}
                    """)
                    print(f"  ✓ 添加字段: {field_name} ({field_type})")
                except Exception as e:
                    print(f"  ✗ 添加字段失败 {field_name}: {e}")
        else:
            print("\n✓ files表结构完整")
        
        # 检查file_history表
        print("\n" + "=" * 60)
        print("检查 file_history 表")
        print("=" * 60)
        cursor.execute("PRAGMA table_info(file_history)")
        columns = {col[1]: col[2] for col in cursor.fetchall()}
        
        print(f"当前字段数: {len(columns)}")
        for col_name, col_type in columns.items():
            print(f"  ✓ {col_name} ({col_type})")
        
        # 需要添加的字段
        missing_fields = []
        
        if 'compressed_size' not in columns:
            missing_fields.append(('compressed_size', 'BIGINT'))
        
        if missing_fields:
            print(f"\n⚠️  缺少 {len(missing_fields)} 个字段，开始添加...")
            for field_name, field_type in missing_fields:
                try:
                    cursor.execute(f"""
                        ALTER TABLE file_history ADD COLUMN {field_name} {field_type}
                    """)
                    print(f"  ✓ 添加字段: {field_name} ({field_type})")
                except Exception as e:
                    print(f"  ✗ 添加字段失败 {field_name}: {e}")
        else:
            print("\n✓ file_history表结构完整")
        
        conn.commit()
        
        # 最终验证
        print("\n" + "=" * 60)
        print("最终验证")
        print("=" * 60)
        
        cursor.execute("PRAGMA table_info(files)")
        files_columns = [col[1] for col in cursor.fetchall()]
        
        required_fields = ['is_compressed', 'compressed_size', 'compression_ratio']
        all_present = all(field in files_columns for field in required_fields)
        
        if all_present:
            print("✅ 数据库结构修复成功！")
            print("\nfiles表包含所有必需字段:")
            for field in required_fields:
                print(f"  ✓ {field}")
            print("\n现在可以重启后端服务了")
        else:
            print("❌ 仍有字段缺失:")
            for field in required_fields:
                if field not in files_columns:
                    print(f"  ✗ {field}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 操作失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    check_and_fix_database()

