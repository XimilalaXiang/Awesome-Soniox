# Soniox 实时转录平台

基于 Soniox V3 API 的专业实时语音转文字平台，支持发言人识别和 AI 智能分析。

## ✨ 功能特性

- 🎤 **实时语音转录**：基于 Soniox V3 的高精度实时转录
- 👥 **发言人识别**：自动识别和区分不同的发言人
- 🌊 **流式显示**：实时显示转录内容，低延迟体验
- 🤖 **AI 智能助手**：支持 OpenAI 兼容 API 进行会议总结和问答
- 🎨 **现代化 UI**：简洁的黑白配色，专业的用户界面
- 📱 **响应式设计**：支持桌面和移动设备访问
- 🐳 **容器化部署**：支持 Docker 一键部署

## 🏗️ 技术架构

### 后端
- **框架**：FastAPI (Python 3.11+)
- **实时通信**：WebSocket
- **语音识别**：Soniox V3 API
- **AI 集成**：OpenAI 兼容 API

### 前端
- **框架**：Vue 3 + Vite
- **状态管理**：Pinia
- **样式**：Tailwind CSS
- **路由**：Vue Router

## 📋 系统要求

- Ubuntu 20.04+ 或其他 Linux 发行版
- Docker 20.10+ 和 Docker Compose
- 或者：Python 3.11+ 和 Node.js 20+（用于本地开发）

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

1. **克隆项目**
```bash
git clone <repository-url>
cd Awesone-Soniox
```

2. **启动服务**
```bash
docker-compose up -d
```

3. **访问应用**
打开浏览器访问 `http://localhost` 或 `http://your-server-ip`

4. **停止服务**
```bash
docker-compose down
```

### 方式二：本地开发部署

#### 后端设置

1. **进入后端目录**
```bash
cd backend
```

2. **创建虚拟环境**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **启动后端服务**
```bash
python main.py
# 或者
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

后端服务将在 `http://localhost:8000` 运行

#### 前端设置

1. **进入前端目录**
```bash
cd frontend
```

2. **安装依赖**
```bash
npm install
```

3. **启动开发服务器**
```bash
npm run dev
```

前端服务将在 `http://localhost:3000` 运行

4. **构建生产版本**
```bash
npm run build
```

## ⚙️ 配置说明

### Soniox API 配置

1. 访问 [Soniox Console](https://soniox.com/console) 创建账户
2. 在项目中创建 API Key
3. 在应用的配置面板中输入 API Key

**配置项：**
- `API Key`：你的 Soniox API 密钥
- `模型`：选择 `stt-rt-v3`（推荐）或 `stt-rt-preview`
- `发言人识别`：启用后可以自动识别不同的发言人

### OpenAI API 配置

用于会议总结和智能问答功能。

**配置项：**
- `API URL`：OpenAI 兼容的 API 地址
  - OpenAI：`https://api.openai.com/v1`
  - 其他兼容服务：根据服务提供商文档配置
- `API Key`：你的 API 密钥
- `模型`：模型 ID（如 `gpt-4o-mini`, `gpt-4`, `gpt-3.5-turbo` 等）

**支持的 OpenAI 兼容服务：**
- OpenAI
- Azure OpenAI
- 其他兼容 OpenAI API 格式的服务

## 📖 使用指南

### 1. 配置 API

首次使用时，点击右上角的"配置"按钮，输入：
- Soniox API Key
- OpenAI API 配置（可选）

配置会自动保存在浏览器本地。

### 2. 开始录音

1. 点击"开始录音"按钮
2. 浏览器会请求麦克风权限，请允许
3. 开始说话，转录内容会实时显示
4. 不同的发言人会用不同的颜色区分

### 3. 控制录音

- **完成当前句**：强制完成当前正在识别的句子
- **停止录音**：结束录音会话
- **清空**：清空当前的转录内容

### 4. 使用 AI 助手

录音完成后，可以使用 AI 助手功能：

**快捷操作：**
- 📝 总结要点
- 📋 按主题总结
- ✅ 提取待办事项

**自定义提问：**
在输入框中输入任何问题，AI 会基于转录内容回答。

## 🔧 高级配置

### 修改端口

**Docker 部署：**
编辑 `docker-compose.yml` 文件：
```yaml
services:
  frontend:
    ports:
      - "8080:80"  # 修改为你想要的端口
```

**本地开发：**
- 后端：修改 `backend/main.py` 中的端口参数
- 前端：修改 `frontend/vite.config.js` 中的 `server.port`

### 启用 HTTPS

对于生产环境，建议使用 Nginx 或 Caddy 作为反向代理并配置 SSL 证书。

**Nginx 示例配置：**
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws/ {
        proxy_pass http://localhost:80/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
}
```

## 🐛 常见问题

### 1. 无法连接到后端

**检查：**
- 后端服务是否正常运行
- 防火墙是否允许端口访问
- 浏览器控制台是否有错误信息

### 2. 麦克风无法使用

**检查：**
- 浏览器是否有麦克风权限
- 必须使用 HTTPS 或 localhost（浏览器安全策略）
- 系统麦克风设备是否正常

### 3. WebSocket 连接失败

**检查：**
- Nginx 配置是否正确设置了 WebSocket 代理
- 防火墙是否允许 WebSocket 连接
- 浏览器是否支持 WebSocket

### 4. Soniox API 错误

**常见原因：**
- API Key 无效或过期
- 账户配额不足
- 网络连接问题

### 5. OpenAI API 错误

**常见原因：**
- API Key 无效
- API URL 配置错误
- 模型 ID 不存在或无权访问

## 📊 系统监控

### 查看日志

**Docker 部署：**
```bash
# 查看后端日志
docker logs soniox-backend

# 查看前端日志
docker logs soniox-frontend

# 实时跟踪日志
docker logs -f soniox-backend
```

**本地部署：**
- 后端日志会直接输出到终端
- 前端日志在浏览器开发者工具中查看

## 🔒 安全建议

1. **不要在客户端暴露 API Key**
   - 当前实现将配置存储在浏览器本地
   - 生产环境建议在后端管理 API Key

2. **使用 HTTPS**
   - 生产环境必须使用 HTTPS
   - 保护 WebSocket 通信安全

3. **限制访问**
   - 配置防火墙规则
   - 使用身份验证（可扩展实现）

## 🛣️ 路线图

- [ ] 用户认证和授权
- [ ] 会话历史保存到数据库
- [ ] 导出转录内容（TXT, PDF, JSON）
- [ ] 支持上传音频文件转录
- [ ] 多语言界面支持
- [ ] 自定义发言人标签
- [ ] 实时翻译功能

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 支持

如有问题，请：
1. 查看文档和常见问题
2. 搜索已有的 Issue
3. 创建新的 Issue

## 🙏 致谢

- [Soniox](https://soniox.com) - 提供优秀的语音识别 API
- [Vue.js](https://vuejs.org) - 前端框架
- [FastAPI](https://fastapi.tiangolo.com) - 后端框架
- [Tailwind CSS](https://tailwindcss.com) - CSS 框架

## 📚 相关链接

- [Soniox 官方文档](https://soniox.com/docs)
- [Soniox API 参考](https://soniox.com/docs/stt/api-reference)
- [OpenAI API 文档](https://platform.openai.com/docs)
