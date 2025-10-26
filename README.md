# WeChatCircle Auto-Reply Service

## Project Introduction

This is a WeChatCircle auto-reply backend service developed based on FastAPI. It can automatically generate reply content according to the user-provided WeChatCircle content and specified reply style.

## Features

- Generate automatic replies based on WeChatCircle content and reply style
- Support multiple reply styles: humorous, serious, ambiguous, warm, critical
- Intelligently determine whether it's the first reply, using different generation strategies for first and non-first replies
- Save reply history and support context understanding
- Automatically generate summaries when the number of replies exceeds 20 to adapt to context window limitations
- Support both Redis and memory storage methods
- Limit reply content to 50 characters, which can include text and WeChat emojis

## Technology Stack

- Python 3.8+
- FastAPI
- Redis (optional)
- OpenAI API (for generating reply content)

## Installation and Deployment

### 1. Clone the Project

```bash
git clone <project repository URL>
cd <project directory>
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy the `.env` file and modify the configuration according to your actual situation:

```bash
cp .env.example .env
# Edit the .env file and fill in the necessary configuration information
```

### 4. Start the Service

```bash
# Start in development mode
python src/app.py

# Or start with uvicorn
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
```

After the service starts, you can access the API documentation through the following address:
http://localhost:8000/docs

## API Interfaces

### 1. Generate Reply

**URL**: `/generate_reply`
**Method**: `POST`
**Request Body**:

```json
{
  "circle_content": "The weather is nice today!",
  "reply_style": "humorous",
  "user_id": "user123",
  "post_id": "post456",
  "previous_replies": []
}
```

**Response**:

```json
{
  "reply_content": "Haha, it's really nice, perfect for going out and having fun~ 😄",
  "is_first_reply": true,
  "timestamp": "2024-01-01T12:00:00"
}
```

### 2. Get Reply History

**URL**: `/reply_history/{user_id}/{post_id}`
**Method**: `GET`
**Response**:

```json
{
  "user_id": "user123",
  "post_id": "post456",
  "reply_count": 3,
  "replies": ["Reply 1", "Reply 2", "Reply 3"]
}
```

### 3. Delete Reply History

**URL**: `/reply_history/{user_id}/{post_id}`
**Method**: `DELETE`
**Response**:

```json
{
  "message": "Reply history deleted"
}
```

### 4. Health Check

**URL**: `/health`
**Method**: `GET`
**Response**:

```json
{
  "status": "healthy",
  "redis_status": "connected",
  "timestamp": "2024-01-01T12:00:00"
}
```

## Notes

1. This service requires an OpenAI API key to generate reply content normally. Please ensure it is correctly configured in the `.env` file.
2. Redis is optional. If Redis is not configured, the service will automatically use memory storage.
3. The service will automatically handle context length limitations and generate summaries when the number of replies exceeds 20.
4. Generated reply content will undergo length limitation and compliance checks.

## License

MIT License