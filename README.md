# 微信朋友圈自动回复服务

## 项目简介

这是一个基于FastAPI开发的微信朋友圈自动回复后端服务，可以根据用户提供的朋友圈内容和指定的回复风格，自动生成符合要求的回复内容。

## 功能特性

- 根据朋友圈内容和回复风格生成自动回复
- 支持多种回复风格：幽默、严肃、暧昧、温馨、批评
- 智能判断是否为首次回复，首次回复和非首次回复采用不同的生成策略
- 保存回复历史，支持上下文理解
- 当回复数量超过20条时，自动生成摘要以适应上下文窗口限制
- 支持Redis和内存两种存储方式
- 回复内容限制在50字以内，可包含文字和微信表情包

## 技术栈

- Python 3.8+
- FastAPI
- Redis (可选)
- OpenAI API (用于生成回复内容)

## 安装部署

### 1. 克隆项目

```bash
git clone <项目仓库地址>
cd <项目目录>
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制`.env`文件并根据实际情况修改配置：

```bash
cp .env.example .env
# 编辑.env文件，填入必要的配置信息
```

### 4. 启动服务

```bash
# 开发模式启动
python app.py

# 或使用uvicorn启动
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后，可以通过以下地址访问API文档：
http://localhost:8000/docs

## API接口

### 1. 生成回复

**URL**: `/generate_reply`
**方法**: `POST`
**请求体**:

```json
{
  "circle_content": "今天天气真好！",
  "reply_style": "幽默",
  "user_id": "user123",
  "post_id": "post456",
  "previous_replies": []
}
```

**响应**:

```json
{
  "reply_content": "哈哈，确实不错，适合出门浪~ 😄",
  "is_first_reply": true,
  "timestamp": "2024-01-01T12:00:00"
}
```

### 2. 获取回复历史

**URL**: `/reply_history/{user_id}/{post_id}`
**方法**: `GET`
**响应**:

```json
{
  "user_id": "user123",
  "post_id": "post456",
  "reply_count": 3,
  "replies": ["回复1", "回复2", "回复3"]
}
```

### 3. 删除回复历史

**URL**: `/reply_history/{user_id}/{post_id}`
**方法**: `DELETE`
**响应**:

```json
{
  "message": "回复历史已删除"
}
```

### 4. 健康检查

**URL**: `/health`
**方法**: `GET`
**响应**:

```json
{
  "status": "healthy",
  "redis_status": "connected",
  "timestamp": "2024-01-01T12:00:00"
}
```

## 注意事项

1. 本服务需要OpenAI API密钥才能正常生成回复内容，请确保在`.env`文件中正确配置
2. Redis是可选的，如果不配置Redis，服务将自动使用内存存储
3. 服务会自动处理上下文长度限制，当回复数量超过20条时生成摘要
4. 生成的回复内容会进行长度限制和合规性检查

## 许可证

MIT License