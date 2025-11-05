#!/bin/bash

# Soniox 实时转录平台启动脚本

echo "🚀 启动 Soniox 实时转录平台..."

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: Docker 未安装"
    echo "请访问 https://docs.docker.com/get-docker/ 安装 Docker"
    exit 1
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "❌ 错误: Docker Compose 未安装"
    echo "请访问 https://docs.docker.com/compose/install/ 安装 Docker Compose"
    exit 1
fi

# 停止旧容器
echo "🛑 停止旧容器..."
docker-compose down

# 构建和启动服务
echo "🔨 构建和启动服务..."
docker-compose up -d --build

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 5

# 检查服务状态
echo "📊 检查服务状态..."
docker-compose ps

echo ""
echo "✅ 启动完成！"
echo ""
echo "📱 访问地址："
echo "   - 前端: http://localhost"
echo "   - 后端 API: http://localhost:8000"
echo ""
echo "📝 查看日志："
echo "   docker logs -f soniox-backend"
echo "   docker logs -f soniox-frontend"
echo ""
echo "🛑 停止服务："
echo "   docker-compose down"
