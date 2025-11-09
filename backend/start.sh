#!/bin/bash
# 后端启动脚本 (Linux/Mac)

echo "🚀 启动Cloud Drive后端服务..."

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "📥 安装依赖..."
pip install -r requirements.txt

# 检查.env文件
if [ ! -f ".env" ]; then
    echo "⚠️  警告: .env文件不存在，请从env.example复制并配置"
    cp env.example .env
    echo "📝 请编辑 .env 文件填入你的AWS凭证"
    exit 1
fi

# 初始化数据库
echo "💾 初始化数据库..."
python3 -c "from app.models.database import init_db; init_db()" 2>/dev/null || true

# 启动服务
echo "✨ 启动服务..."
echo "📍 API地址: http://0.0.0.0:8000"
echo "📖 API文档: http://0.0.0.0:8000/docs"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

