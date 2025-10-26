from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import redis
import json
import os
from datetime import datetime
from dotenv import load_dotenv
import openai

# 加载环境变量
load_dotenv()

# 初始化FastAPI应用
app = FastAPI(
    title="微信朋友圈自动回复服务",
    description="提供朋友圈自动回复生成功能",
    version="1.0.0"
)

# 初始化Redis连接（如果环境中有配置）
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_AVAILABLE = False
redis_client = None

try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)
    redis_client.ping()
    REDIS_AVAILABLE = True
    print("Redis连接成功")
except Exception as e:
    print(f"Redis连接失败，将使用内存存储: {str(e)}")

# 内存存储，用于缓存用户的回复历史
memory_storage: Dict[str, List[Dict]] = {}

# 配置OpenAI API（根据实际使用的大模型调整）
openai.api_key = os.getenv("OPENAI_API_KEY", "")

# 定义数据模型
class ReplyRequest(BaseModel):
    circle_content: str = Field(..., description="朋友圈内容")
    reply_style: str = Field(..., description="回复风格：幽默，严肃，暧昧，温馨，批评")
    user_id: str = Field(..., description="用户唯一标识")
    post_id: str = Field(..., description="朋友圈帖子唯一标识")
    previous_replies: Optional[List[str]] = Field(default=[], description="之前的回复内容列表")

class ReplyResponse(BaseModel):
    reply_content: str = Field(..., description="生成的回复内容")
    is_first_reply: bool = Field(..., description="是否是第一次回复")
    timestamp: datetime = Field(..., description="生成时间戳")

# 验证回复风格
valid_styles = ["幽默", "严肃", "暧昧", "温馨", "批评"]

# 生成回复内容的核心函数
def generate_reply(circle_content: str, reply_style: str, 
                  is_first_reply: bool, previous_replies: List[str] = None):
    """
    调用大模型生成回复内容
    """
    try:
        # 构建提示词
        if is_first_reply:
            prompt = f"""请生成一个{reply_style}风格的朋友圈回复。
朋友圈内容: {circle_content}
回复要求:
1. 回复风格必须是{reply_style}
2. 内容限定50字以内
3. 可以包含文字和微信表情包
4. 内容必须符合中国法律法规
5. 直接输出回复内容，不要添加其他解释"""
        else:
            # 构建包含历史回复的提示词
            history_text = "\n之前的回复:\n"
            for i, reply in enumerate(previous_replies[-10:], 1):  # 只保留最近10条
                history_text += f"{i}. {reply}\n"
            
            prompt = f"""请生成一个{reply_style}风格的朋友圈回复。
朋友圈内容: {circle_content}
{history_text}
回复要求:
1. 回复风格必须是{reply_style}
2. 内容限定50字以内
3. 可以包含文字和微信表情包
4. 内容必须符合中国法律法规
5. 直接输出回复内容，不要添加其他解释"""
        
        # 调用OpenAI API (模拟实现，实际使用时需要根据具体API调整)
        # 这里为了演示，返回模拟内容
        # 实际项目中替换为真实的API调用
        
        # 模拟回复生成
        mock_replies = {
            "幽默": "哈哈，说得太对了！😂",
            "严肃": "你说得很有道理，值得深思。",
            "暧昧": "这个分享很特别呢~ 😊",
            "温馨": "看完很温暖，谢谢分享~ 🌟",
            "批评": "我认为这个观点还有待商榷。"
        }
        
        reply = mock_replies.get(reply_style, "很有意思的分享！")
        
        # 实际调用示例（需要API密钥）:
        # response = openai.chat.completions.create(
        #     model="gpt-3.5-turbo",
        #     messages=[{"role": "user", "content": prompt}],
        #     max_tokens=100,
        #     temperature=0.7
        # )
        # reply = response.choices[0].message.content.strip()
        
        # 确保回复长度不超过50字
        if len(reply) > 50:
            reply = reply[:50]
        
        return reply
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成回复时出错: {str(e)}")

# 生成回复摘要的函数
def generate_reply_summary(replies: List[str]):
    """
    当回复数量超过20条时，生成摘要
    """
    try:
        prompt = f"""请将以下朋友圈回复内容生成一个简短的摘要，保留关键信息和讨论主题。
回复内容:
{"\n".join(replies)}
摘要要求简洁，不超过100字。"""
        
        # 模拟摘要生成
        summary = f"关于这条朋友圈的讨论涉及了多个方面，共有{len(replies)}条回复..."
        
        # 实际调用示例:
        # response = openai.chat.completions.create(
        #     model="gpt-3.5-turbo",
        #     messages=[{"role": "user", "content": prompt}],
        #     max_tokens=150,
        #     temperature=0.3
        # )
        # summary = response.choices[0].message.content.strip()
        
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成摘要时出错: {str(e)}")

# 保存回复历史
def save_reply_history(user_id: str, post_id: str, reply: str):
    """
    保存回复历史到内存或Redis
    """
    key = f"{user_id}:{post_id}"
    
    # 获取现有历史
    if REDIS_AVAILABLE:
        # 使用Redis存储
        history_data = redis_client.get(key)
        if history_data:
            history = json.loads(history_data)
        else:
            history = []
        
        # 添加新回复
        history.append({
            "reply": reply,
            "timestamp": datetime.now().isoformat()
        })
        
        # 检查是否需要生成摘要
        if len(history) > 20:
            # 提取所有回复内容
            replies = [item["reply"] for item in history]
            # 生成摘要
            summary = generate_reply_summary(replies)
            # 保留摘要和最近几条回复
            history = [
                {"type": "summary", "content": summary, "timestamp": datetime.now().isoformat()},
                *history[-5:]
            ]
        
        # 保存回Redis
        redis_client.setex(key, 60*60*24*7, json.dumps(history))  # 保存7天
    else:
        # 使用内存存储
        if key not in memory_storage:
            memory_storage[key] = []
        
        memory_storage[key].append({
            "reply": reply,
            "timestamp": datetime.now().isoformat()
        })
        
        # 检查是否需要生成摘要
        if len(memory_storage[key]) > 20:
            # 提取所有回复内容
            replies = [item["reply"] for item in memory_storage[key]]
            # 生成摘要
            summary = generate_reply_summary(replies)
            # 保留摘要和最近几条回复
            memory_storage[key] = [
                {"type": "summary", "content": summary, "timestamp": datetime.now().isoformat()},
                *memory_storage[key][-5:]
            ]

# 获取回复历史
def get_reply_history(user_id: str, post_id: str) -> List[str]:
    """
    从内存或Redis获取回复历史
    """
    key = f"{user_id}:{post_id}"
    history = []
    
    if REDIS_AVAILABLE:
        # 从Redis获取
        history_data = redis_client.get(key)
        if history_data:
            history = json.loads(history_data)
    else:
        # 从内存获取
        if key in memory_storage:
            history = memory_storage[key]
    
    # 提取回复内容，过滤摘要
    replies = []
    for item in history:
        if item.get("type") == "summary":
            # 如果是摘要，将其作为上下文的一部分
            replies.append(f"[讨论摘要] {item['content']}")
        else:
            replies.append(item.get("reply", ""))
    
    return replies

# 检查是否是第一次回复
def is_first_reply(user_id: str, post_id: str) -> bool:
    """
    检查用户对某条朋友圈是否是第一次回复
    """
    history = get_reply_history(user_id, post_id)
    # 如果没有历史回复，或者只有摘要（摘要不算实际回复），则视为第一次回复
    actual_replies = [r for r in history if not r.startswith("[讨论摘要]")]
    return len(actual_replies) == 0

# API端点：生成回复
@app.post("/generate_reply", response_model=ReplyResponse)
async def generate_reply_endpoint(request: ReplyRequest):
    # 验证回复风格
    if request.reply_style not in valid_styles:
        raise HTTPException(status_code=400, detail=f"无效的回复风格，必须是以下之一: {', '.join(valid_styles)}")
    
    # 验证朋友圈内容
    if not request.circle_content or len(request.circle_content) == 0:
        raise HTTPException(status_code=400, detail="朋友圈内容不能为空")
    
    # 检查是否是第一次回复
    first_reply = is_first_reply(request.user_id, request.post_id)
    
    # 获取历史回复
    history_replies = get_reply_history(request.user_id, request.post_id)
    
    # 生成回复
    reply_content = generate_reply(
        circle_content=request.circle_content,
        reply_style=request.reply_style,
        is_first_reply=first_reply,
        previous_replies=history_replies
    )
    
    # 保存新回复
    save_reply_history(request.user_id, request.post_id, reply_content)
    
    # 返回结果
    return ReplyResponse(
        reply_content=reply_content,
        is_first_reply=first_reply,
        timestamp=datetime.now()
    )

# API端点：获取回复历史
@app.get("/reply_history/{user_id}/{post_id}")
async def get_reply_history_endpoint(user_id: str, post_id: str):
    history = get_reply_history(user_id, post_id)
    return {
        "user_id": user_id,
        "post_id": post_id,
        "reply_count": len(history),
        "replies": history
    }

# API端点：删除回复历史
@app.delete("/reply_history/{user_id}/{post_id}")
async def delete_reply_history_endpoint(user_id: str, post_id: str):
    key = f"{user_id}:{post_id}"
    
    if REDIS_AVAILABLE:
        redis_client.delete(key)
    elif key in memory_storage:
        del memory_storage[key]
    
    return {"message": "回复历史已删除"}

# 健康检查端点
@app.get("/health")
async def health_check():
    redis_status = "connected" if REDIS_AVAILABLE else "disconnected"
    return {
        "status": "healthy",
        "redis_status": redis_status,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)