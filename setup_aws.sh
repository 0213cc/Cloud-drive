#!/bin/bash
# AWS S3快速配置脚本
# 在远程Ubuntu EC2上运行

echo "🔧 Cloud Drive - AWS S3 配置向导"
echo "=================================="
echo ""

# 检查AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI未安装"
    echo "📥 正在安装AWS CLI..."
    sudo apt update
    sudo apt install awscli -y
fi

echo "✅ AWS CLI已安装"
echo ""

# 配置AWS凭证
echo "📝 配置AWS凭证"
echo "请输入你的AWS Access Key ID："
read -r AWS_KEY

echo "请输入你的AWS Secret Access Key："
read -rs AWS_SECRET
echo ""

echo "请输入AWS区域 (默认: ap-northeast-1)："
read -r AWS_REGION
AWS_REGION=${AWS_REGION:-ap-northeast-1}

# 配置AWS CLI
aws configure set aws_access_key_id "$AWS_KEY"
aws configure set aws_secret_access_key "$AWS_SECRET"
aws configure set default.region "$AWS_REGION"
aws configure set default.output json

echo ""
echo "✅ AWS凭证配置完成"
echo ""

# 测试连接
echo "🔍 测试AWS连接..."
if aws s3 ls &> /dev/null; then
    echo "✅ AWS连接成功"
else
    echo "❌ AWS连接失败，请检查凭证"
    exit 1
fi

echo ""

# 创建S3存储桶
echo "📦 创建S3存储桶"
echo "请输入存储桶名称（必须全局唯一，建议: cloud-drive-yourname-$(date +%s)）："
read -r BUCKET_NAME

if [ -z "$BUCKET_NAME" ]; then
    BUCKET_NAME="cloud-drive-$(whoami)-$(date +%s)"
    echo "使用默认名称: $BUCKET_NAME"
fi

echo ""
echo "🚀 创建存储桶: $BUCKET_NAME"

if aws s3 mb "s3://$BUCKET_NAME" --region "$AWS_REGION"; then
    echo "✅ 存储桶创建成功: $BUCKET_NAME"
else
    echo "⚠️  存储桶可能已存在或名称冲突"
    echo "继续使用此名称..."
fi

echo ""

# 设置CORS（可选）
echo "🔐 配置存储桶CORS策略..."
cat > /tmp/cors.json << 'EOF'
{
  "CORSRules": [
    {
      "AllowedHeaders": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
      "AllowedOrigins": ["*"],
      "ExposeHeaders": ["ETag"]
    }
  ]
}
EOF

aws s3api put-bucket-cors --bucket "$BUCKET_NAME" --cors-configuration file:///tmp/cors.json 2>/dev/null
rm /tmp/cors.json

echo ""

# 测试上传
echo "🧪 测试文件上传..."
echo "Hello Cloud Drive!" > /tmp/test.txt

if aws s3 cp /tmp/test.txt "s3://$BUCKET_NAME/test.txt"; then
    echo "✅ 上传测试成功"
    aws s3 rm "s3://$BUCKET_NAME/test.txt" > /dev/null
    echo "✅ 删除测试文件"
else
    echo "❌ 上传测试失败"
    exit 1
fi

rm /tmp/test.txt

echo ""
echo "=================================="
echo "✅ AWS S3配置完成！"
echo "=================================="
echo ""
echo "📋 配置信息："
echo "   区域: $AWS_REGION"
echo "   存储桶: $BUCKET_NAME"
echo ""
echo "📝 下一步："
echo "   1. 将以下信息添加到后端 .env 文件："
echo ""
echo "      AWS_ACCESS_KEY_ID=$AWS_KEY"
echo "      AWS_SECRET_ACCESS_KEY=***隐藏***"
echo "      AWS_REGION=$AWS_REGION"
echo "      AWS_S3_BUCKET=$BUCKET_NAME"
echo ""
echo "   2. 启动后端服务："
echo "      cd ~/cloud-drive/backend"
echo "      source venv/bin/activate"
echo "      python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "🎉 配置完成！"

