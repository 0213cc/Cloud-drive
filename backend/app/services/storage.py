"""
S3存储服务 - 支持多线程上传下载
"""
import boto3
import os
import hashlib
from typing import BinaryIO, Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError
from config import get_settings
import io
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class S3StorageService:
    """S3存储服务"""
    
    def __init__(self):
        """初始化S3客户端"""
        # 如果提供了Access Key，使用显式凭证
        # 否则boto3会自动使用EC2 IAM角色（更安全）
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            logger.info("Using explicit AWS credentials (Access Key)")
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region
            )
        else:
            logger.info("Using IAM role credentials (EC2 Instance Profile)")
            self.s3_client = boto3.client(
                's3',
                region_name=settings.aws_region
            )
        
        self.bucket_name = settings.aws_s3_bucket
        self.chunk_size = settings.chunk_size
        self.max_concurrency = settings.max_concurrency
        self.multipart_threshold = settings.multipart_threshold
    
    def calculate_file_hash(self, file_obj: BinaryIO) -> str:
        """
        计算文件的SHA-256哈希值
        
        Args:
            file_obj: 文件对象
            
        Returns:
            十六进制哈希字符串
        """
        sha256_hash = hashlib.sha256()
        file_obj.seek(0)
        
        for byte_block in iter(lambda: file_obj.read(4096), b""):
            sha256_hash.update(byte_block)
        
        file_obj.seek(0)
        return sha256_hash.hexdigest()
    
    def upload_file_simple(
        self, 
        file_obj: BinaryIO, 
        s3_key: str,
        content_type: Optional[str] = None
    ) -> Dict:
        """
        简单上传（小文件）
        
        Args:
            file_obj: 文件对象
            s3_key: S3对象键
            content_type: 文件MIME类型
            
        Returns:
            上传结果字典
        """
        try:
            file_obj.seek(0)
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            response = self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_obj,
                **extra_args
            )
            
            return {
                'success': True,
                'etag': response.get('ETag', '').strip('"'),
                's3_key': s3_key
            }
        except ClientError as e:
            logger.error(f"上传失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def upload_file_multipart(
        self, 
        file_obj: BinaryIO, 
        s3_key: str,
        file_size: int,
        content_type: Optional[str] = None
    ) -> Dict:
        """
        多线程分块上传（大文件）
        
        Args:
            file_obj: 文件对象
            s3_key: S3对象键
            file_size: 文件大小
            content_type: 文件MIME类型
            
        Returns:
            上传结果字典
        """
        try:
            # 1. 初始化分块上传
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            response = self.s3_client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=s3_key,
                **extra_args
            )
            upload_id = response['UploadId']
            
            # 2. 计算分块
            num_parts = (file_size + self.chunk_size - 1) // self.chunk_size
            parts = []
            
            logger.info(f"开始多线程上传: {num_parts} 个分块")
            
            # 3. 定义上传单个分块的函数
            def upload_part(part_number: int, start: int, end: int):
                file_obj.seek(start)
                data = file_obj.read(end - start)
                
                response = self.s3_client.upload_part(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    Body=data
                )
                
                return {
                    'PartNumber': part_number,
                    'ETag': response['ETag']
                }
            
            # 4. 使用线程池并发上传
            with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
                futures = []
                
                for i in range(num_parts):
                    start = i * self.chunk_size
                    end = min(start + self.chunk_size, file_size)
                    part_number = i + 1
                    
                    future = executor.submit(upload_part, part_number, start, end)
                    futures.append(future)
                
                # 收集结果
                for future in as_completed(futures):
                    part = future.result()
                    parts.append(part)
                    logger.info(f"分块 {part['PartNumber']}/{num_parts} 上传完成")
            
            # 5. 完成分块上传
            parts.sort(key=lambda x: x['PartNumber'])
            
            response = self.s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=s3_key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            
            logger.info(f"多线程上传完成: {s3_key}")
            
            return {
                'success': True,
                'etag': response.get('ETag', '').strip('"'),
                's3_key': s3_key,
                'parts': len(parts)
            }
            
        except Exception as e:
            logger.error(f"多线程上传失败: {e}")
            # 取消上传
            try:
                self.s3_client.abort_multipart_upload(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    UploadId=upload_id
                )
            except:
                pass
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def upload_file(
        self, 
        file_obj: BinaryIO, 
        s3_key: str,
        file_size: int,
        content_type: Optional[str] = None
    ) -> Dict:
        """
        智能上传：根据文件大小选择上传方式
        
        Args:
            file_obj: 文件对象
            s3_key: S3对象键
            file_size: 文件大小
            content_type: 文件MIME类型
            
        Returns:
            上传结果字典
        """
        if file_size > self.multipart_threshold:
            logger.info(f"使用多线程上传 (文件大小: {file_size / 1024 / 1024:.2f} MB)")
            return self.upload_file_multipart(file_obj, s3_key, file_size, content_type)
        else:
            logger.info(f"使用简单上传 (文件大小: {file_size / 1024 / 1024:.2f} MB)")
            return self.upload_file_simple(file_obj, s3_key, content_type)
    
    def download_file_simple(self, s3_key: str, output_path: str) -> Dict:
        """
        简单下载（小文件）
        
        Args:
            s3_key: S3对象键
            output_path: 输出文件路径
            
        Returns:
            下载结果字典
        """
        try:
            self.s3_client.download_file(
                self.bucket_name,
                s3_key,
                output_path
            )
            
            return {
                'success': True,
                'path': output_path
            }
        except ClientError as e:
            logger.error(f"下载失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def download_file_multithread(
        self, 
        s3_key: str, 
        output_path: str,
        file_size: int
    ) -> Dict:
        """
        多线程分块下载（大文件）
        
        Args:
            s3_key: S3对象键
            output_path: 输出文件路径
            file_size: 文件大小
            
        Returns:
            下载结果字典
        """
        try:
            # 1. 计算分块
            num_parts = (file_size + self.chunk_size - 1) // self.chunk_size
            
            logger.info(f"开始多线程下载: {num_parts} 个分块")
            
            # 2. 定义下载单个分块的函数
            def download_part(part_number: int, start: int, end: int):
                range_header = f'bytes={start}-{end-1}'
                
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Range=range_header
                )
                
                data = response['Body'].read()
                return part_number, start, data
            
            # 3. 创建输出文件
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 4. 使用线程池并发下载
            with open(output_path, 'wb') as f:
                # 预分配文件大小
                f.seek(file_size - 1)
                f.write(b'\0')
                f.seek(0)
                
                with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
                    futures = []
                    
                    for i in range(num_parts):
                        start = i * self.chunk_size
                        end = min(start + self.chunk_size, file_size)
                        part_number = i + 1
                        
                        future = executor.submit(download_part, part_number, start, end)
                        futures.append(future)
                    
                    # 收集结果并写入文件
                    for future in as_completed(futures):
                        part_number, start, data = future.result()
                        f.seek(start)
                        f.write(data)
                        logger.info(f"分块 {part_number}/{num_parts} 下载完成")
            
            logger.info(f"多线程下载完成: {output_path}")
            
            return {
                'success': True,
                'path': output_path,
                'parts': num_parts
            }
            
        except Exception as e:
            logger.error(f"多线程下载失败: {e}")
            # 删除不完整的文件
            if os.path.exists(output_path):
                os.remove(output_path)
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def download_file(self, s3_key: str, output_path: str) -> Dict:
        """
        智能下载：根据文件大小选择下载方式
        
        Args:
            s3_key: S3对象键
            output_path: 输出文件路径
            
        Returns:
            下载结果字典
        """
        try:
            # 获取文件大小
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            file_size = response['ContentLength']
            
            if file_size > self.multipart_threshold:
                logger.info(f"使用多线程下载 (文件大小: {file_size / 1024 / 1024:.2f} MB)")
                return self.download_file_multithread(s3_key, output_path, file_size)
            else:
                logger.info(f"使用简单下载 (文件大小: {file_size / 1024 / 1024:.2f} MB)")
                return self.download_file_simple(s3_key, output_path)
                
        except ClientError as e:
            logger.error(f"获取文件信息失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def copy_file(self, source_key: str, destination_key: str) -> Dict:
        """
        在S3中复制文件

        Args:
            source_key: 源对象键
            destination_key: 目标对象键

        Returns:
            复制结果字典
        """
        try:
            copy_source = {
                'Bucket': self.bucket_name,
                'Key': source_key
            }
            response = self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket_name,
                Key=destination_key
            )
            
            etag = response.get('CopyObjectResult', {}).get('ETag', '').strip('"')

            logger.info(f"文件已从 {source_key} 复制到 {destination_key}")
            
            return {
                'success': True,
                's3_key': destination_key,
                'etag': etag
            }
        except ClientError as e:
            logger.error(f"S3文件复制失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def delete_file(self, s3_key: str) -> Dict:
        """
        删除文件
        
        Args:
            s3_key: S3对象键
            
        Returns:
            删除结果字典
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            return {
                'success': True,
                's3_key': s3_key
            }
        except ClientError as e:
            logger.error(f"删除失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_objects(self, prefix: str = "") -> List[Dict]:
        """
        列出对象
        
        Args:
            prefix: 前缀（用于模拟目录）
            
        Returns:
            对象列表
        """
        try:
            objects = []
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat(),
                            'etag': obj.get('ETag', '').strip('"')
                        })
            
            return objects
        except ClientError as e:
            logger.error(f"列表获取失败: {e}")
            return []
    
    def file_exists(self, s3_key: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            s3_key: S3对象键
            
        Returns:
            是否存在
        """
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return True
        except ClientError:
            return False
    
    def get_file_metadata(self, s3_key: str) -> Optional[Dict]:
        """
        获取文件元数据
        
        Args:
            s3_key: S3对象键
            
        Returns:
            元数据字典
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            return {
                'size': response['ContentLength'],
                'content_type': response.get('ContentType'),
                'etag': response.get('ETag', '').strip('"'),
                'last_modified': response['LastModified'].isoformat()
            }
        except ClientError as e:
            logger.error(f"获取元数据失败: {e}")
            return None

