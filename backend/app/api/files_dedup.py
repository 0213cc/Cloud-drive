"""
带文件去重功能的上传逻辑

这个模块包含修改后的上传函数，支持文件级去重
"""

async def upload_file_with_dedup(
    file, path, enable_compression, db, storage, user_id,
    temp_file_path, compressed_file_path, FileModel, FileHistory, logger
):
    """
    上传文件（支持去重）
    
    流程:
    1. 计算文件哈希
    2. 检查是否已存在相同哈希的文件块
    3. 如果存在，复用文件块（去重）
    4. 如果不存在，上传文件并创建新文件块
    5. 创建或更新文件记录
    """
    from app.utils.deduplication import DeduplicationService
    from app.utils.compression import CompressionService
    from datetime import datetime
    import os
    
    # 1. 获取原始文件大小
    original_size = os.path.getsize(temp_file_path)
    
    # 2. 计算原始文件哈希值
    with open(temp_file_path, 'rb') as f:
        hash_value = storage.calculate_file_hash(f)
    
    logger.info(f"文件哈希: {file.filename}, hash={hash_value[:16]}...")
    
    # 3. 检查文件去重 - 是否已存在相同哈希的文件块
    existing_chunk = DeduplicationService.check_duplicate(db, hash_value)
    
    chunk_id = None
    s3_key = None
    s3_etag = None
    is_compressed = False
    compressed_size = original_size
    compression_ratio = 0
    stored_content_type = file.content_type
    is_deduplicated = False
    
    if existing_chunk:
        # 文件已存在，复用现有的文件块（去重）
        chunk_id = existing_chunk.id
        s3_key = existing_chunk.s3_key
        s3_etag = existing_chunk.s3_etag
        is_compressed = existing_chunk.is_compressed
        compressed_size = existing_chunk.compressed_size or original_size
        compression_ratio = existing_chunk.compression_ratio or 0
        stored_content_type = existing_chunk.stored_content_type
        is_deduplicated = True
        
        # 增加引用计数
        DeduplicationService.increment_reference(db, existing_chunk)
        
        logger.info(
            f"✓ 文件去重: {file.filename}, "
            f"复用 chunk_id={chunk_id}, "
            f"跳过上传，节省 {original_size / 1024 / 1024:.2f} MB"
        )
    else:
        # 文件不存在，需要上传
        logger.info(f"新文件，需要上传: {file.filename}")
        
        # 判断是否需要压缩
        should_compress = (
            enable_compression and 
            CompressionService.should_compress(original_size, file.content_type)
        )
        
        logger.info(
            f"压缩检查: enable_compression={enable_compression}, "
            f"file_size={original_size / 1024 / 1024:.2f} MB, "
            f"content_type={file.content_type}, "
            f"should_compress={should_compress}"
        )
        
        upload_file_path = temp_file_path
        
        if should_compress:
            # 压缩文件
            import tempfile as tf
            compressed_file_path = tf.mktemp(suffix='.gz')
            
            with open(temp_file_path, 'rb') as input_f, open(compressed_file_path, 'wb') as output_f:
                compress_result = CompressionService.compress_file(input_f, output_f)
                
                if compress_result['success']:
                    is_compressed = True
                    compressed_size = compress_result['compressed_size']
                    compression_ratio = int(compress_result['compression_ratio'])
                    upload_file_path = compressed_file_path
                    stored_content_type = 'application/gzip'
                    
                    logger.info(
                        f"文件已压缩: {file.filename}, "
                        f"原始: {original_size / 1024 / 1024:.2f} MB, "
                        f"压缩后: {compressed_size / 1024 / 1024:.2f} MB, "
                        f"压缩率: {compression_ratio}%"
                    )
                else:
                    logger.warning(f"压缩失败，使用原始文件: {compress_result.get('error')}")
        
        # 生成唯一的S3键
        timestamp = int(datetime.utcnow().timestamp())
        unique_filename = f"{timestamp}_{file.filename}"
        if is_compressed:
            unique_filename += ".gz"
        
        clean_path = path.strip('/').strip()
        
        if clean_path:
            s3_key = f"users/{user_id}/{clean_path}/{unique_filename}"
        else:
            s3_key = f"users/{user_id}/{unique_filename}"
        
        # 上传到S3
        upload_size = compressed_size if is_compressed else original_size
        
        with open(upload_file_path, 'rb') as f:
            result = storage.upload_file(
                f, 
                s3_key, 
                upload_size,
                stored_content_type
            )
        
        if not result['success']:
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"上传失败: {result.get('error')}")
        
        s3_etag = result.get('etag')
        
        # 创建新的文件块记录
        new_chunk = DeduplicationService.create_chunk(
            db=db,
            hash_value=hash_value,
            size=original_size,
            s3_key=s3_key,
            s3_etag=s3_etag,
            is_compressed=is_compressed,
            compressed_size=compressed_size if is_compressed else None,
            compression_ratio=compression_ratio if is_compressed else None,
            stored_content_type=stored_content_type
        )
        chunk_id = new_chunk.id
    
    # 4. 构建文件路径
    clean_path = path.strip('/').strip()
    if clean_path:
        full_path = f"/{clean_path}/{file.filename}"
    else:
        full_path = f"/{file.filename}"
    
    # 5. 保存元数据到数据库
    existing_file = db.query(FileModel).filter(
        FileModel.user_id == user_id,
        FileModel.path == full_path,
        FileModel.is_directory == False
    ).first()
    
    if existing_file:
        # 文件已存在，保存旧版本到历史记录
        file_history = FileHistory(
            file_id=existing_file.id,
            version=existing_file.version,
            size=existing_file.size,
            hash_value=existing_file.hash_value,
            chunk_id=existing_file.chunk_id,
            s3_key=existing_file.s3_key,
            s3_etag=existing_file.s3_etag,
            is_compressed=existing_file.is_compressed,
            compressed_size=existing_file.compressed_size
        )
        db.add(file_history)
        
        # 如果旧版本也有chunk_id，需要减少其引用计数
        if existing_file.chunk_id and existing_file.chunk_id != chunk_id:
            DeduplicationService.decrement_reference(
                db, existing_file.chunk_id, storage
            )
        
        # 更新现有文件记录
        existing_file.size = original_size
        existing_file.content_type = file.content_type
        existing_file.hash_value = hash_value
        existing_file.chunk_id = chunk_id
        existing_file.s3_key = s3_key
        existing_file.s3_etag = s3_etag
        existing_file.is_compressed = is_compressed
        existing_file.compressed_size = compressed_size if is_compressed else None
        existing_file.compression_ratio = compression_ratio if is_compressed else None
        existing_file.version += 1
        existing_file.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(existing_file)
        db_file = existing_file
    else:
        # 新文件
        db_file = FileModel(
            user_id=user_id,
            path=full_path,
            filename=file.filename,
            size=original_size,
            content_type=file.content_type,
            hash_value=hash_value,
            chunk_id=chunk_id,
            s3_key=s3_key,
            s3_etag=s3_etag,
            is_compressed=is_compressed,
            compressed_size=compressed_size if is_compressed else None,
            compression_ratio=compression_ratio if is_compressed else None,
            is_directory=False,
            version=1
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
    
    # 6. 构建返回消息
    message = "上传成功"
    if is_deduplicated:
        message += f"（文件已存在，去重节省 {original_size / 1024 / 1024:.2f} MB）"
    elif is_compressed:
        message += f"（已压缩，节省 {compression_ratio}% 空间）"
    
    return db_file, message, is_deduplicated

