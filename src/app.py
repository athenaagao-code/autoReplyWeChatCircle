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

class EmotionAnalysisResult(BaseModel):
    emotion_type: str = Field(..., description="情绪类型")
    negative_score: int = Field(..., ge=1, le=10, description="负面程度评分，1-10分")
    emotion_description: str = Field(..., description="情绪描述")

class ReplyResponse(BaseModel):
    reply_content: str = Field(..., description="生成的回复内容")
    is_first_reply: bool = Field(..., description="是否是第一次回复")
    timestamp: datetime = Field(..., description="生成时间戳")
    emotion_analysis: EmotionAnalysisResult = Field(..., description="情感分析结果")

class AdDetectionRequest(BaseModel):
    circle_content: str = Field(..., description="朋友圈内容")
    user_id: str = Field(..., description="用户唯一标识")
    post_id: str = Field(..., description="朋友圈帖子唯一标识")

class AdDetectionResponse(BaseModel):
    is_ad: bool = Field(..., description="是否为广告")
    response_text: str = Field(..., description="响应文本")
    confidence: float = Field(..., ge=0.0, le=1.0, description="检测置信度")
    timestamp: datetime = Field(..., description="检测时间戳")

# 验证回复风格
valid_styles = ["幽默", "严肃", "暧昧", "温馨", "批评"]

# 广告检测关键词列表
ad_keywords = [
    "优惠", "折扣", "促销", "特价", "限时", "秒杀", "抢购",
    "免费领取", "转发抽奖", "添加微信", "扫码关注", "加群",
    "投资", "理财", "赚钱", "兼职", "副业", "日入", "月入",
    "代理", "加盟", "招商", "合伙人", "会员", "VIP", "套餐",
    "咨询电话", "联系方式", "微信", "QQ", "电话", "手机号",
    "网址", "链接", "网址是", "链接是", "点击查看", "点击链接",
    "扫码", "二维码", "长按识别", "识别二维码",
    "正品", "保证", "效果", "神奇", "有效", "彻底", "解决"
]

# 广告检测函数
def detect_ad(text: str) -> Dict:
    """
    检测文本是否为广告内容
    返回包含是否为广告、置信度等信息的字典
    """
    try:
        # 转换为小写进行检测
        text_lower = text.lower()
        
        # 关键词匹配
        matched_keywords = []
        for keyword in ad_keywords:
            if keyword in text_lower:
                matched_keywords.append(keyword)
        
        # 计算置信度（简单实现：根据匹配到的关键词数量和文本长度计算）
        confidence = 0.0
        if text_lower.strip():
            # 基础置信度：匹配关键词数 / 总关键词数
            base_confidence = len(matched_keywords) / len(ad_keywords)
            # 加权：根据关键词在文本中的密度调整
            keyword_density = len(matched_keywords) / max(1, len(text_lower) / 10)  # 每10个字符的关键词数
            confidence = min(1.0, base_confidence * 0.6 + keyword_density * 0.4)
        
        # 判断是否为广告（置信度大于0.3或匹配到2个以上关键词）
        is_ad = confidence > 0.3 or len(matched_keywords) >= 2
        
        # 实际项目中可以使用更复杂的算法或调用专业的广告检测API
        # 例如：
        # response = openai.chat.completions.create(
        #     model="gpt-3.5-turbo",
        #     messages=[
        #         {"role": "system", "content": "你是一个广告内容检测器，专门判断文本是否为广告。"},
        #         {"role": "user", "content": f"请判断以下文本是否为广告，返回JSON格式：{{\"is_ad\": true/false, \"confidence\": 0.0-1.0, \"reason\": \"检测理由\"}}\n\n文本：{text}"}
        #     ],
        #     max_tokens=150,
        #     temperature=0.3
        # )
        # result = json.loads(response.choices[0].message.content.strip())
        
        return {
            "is_ad": is_ad,
            "confidence": confidence,
            "matched_keywords": matched_keywords,
            "reason": f"匹配到{len(matched_keywords)}个广告关键词: {', '.join(matched_keywords)}"
        }
    except Exception as e:
        # 出错时默认返回非广告
        return {
            "is_ad": False,
            "confidence": 0.0,
            "matched_keywords": [],
            "reason": f"广告检测出错: {str(e)}"
        }

# 情感分析函数
def analyze_emotion(text: str):
    """
    分析文本的情感状态，返回情绪类型和负面程度评分
    
    评分规则：
    - 分数范围为1-10
    - 分数越高表示情绪越负面
    - 1-3分：积极正面的情绪
    - 4-5分：中性或轻微情绪波动
    - 6-8分：明显的负面情绪
    - 9-10分：强烈的负面情绪
    """
    try:
        # 构建情感分析提示词
        prompt = f"""请分析以下文本的情感状态：
{text}

请按照以下格式返回分析结果：
1. 情绪类型：[积极/中性/消极/其他具体情绪类型]
2. 负面程度评分：[1-10的数字，1表示最积极，10表示最负面]
3. 情绪描述：[对情绪的简要描述]

评分规则：
- 分数范围为1-10
- 分数越高表示情绪越负面
- 1-3分：积极正面的情绪
- 4-5分：中性或轻微情绪波动
- 6-8分：明显的负面情绪
- 9-10分：强烈的负面情绪"""
        
        # 模拟情感分析结果（实际使用时应替换为真实API调用）
        # 这里根据文本长度和内容特征生成模拟结果
        
        # 简单的模拟逻辑
        if "难过" in text or "伤心" in text or "不开心" in text:
            emotion_type = "消极"
            negative_score = 7
            emotion_description = "表达了悲伤或不开心的情绪"
        elif "开心" in text or "高兴" in text or "快乐" in text:
            emotion_type = "积极"
            negative_score = 2
            emotion_description = "表达了愉悦或开心的情绪"
        elif "生气" in text or "愤怒" in text or "烦" in text:
            emotion_type = "消极"
            negative_score = 8
            emotion_description = "表达了愤怒或烦躁的情绪"
        elif "谢谢" in text or "感谢" in text:
            emotion_type = "积极"
            negative_score = 1
            emotion_description = "表达了感激的情绪"
        elif "压力" in text or "累" in text or "疲惫" in text:
            emotion_type = "消极"
            negative_score = 6
            emotion_description = "表达了压力或疲惫的情绪"
        else:
            # 默认中性
            emotion_type = "中性"
            negative_score = 4
            emotion_description = "情绪较为平静，没有明显的积极或消极倾向"
        
        # 实际调用示例：
        # response = openai.chat.completions.create(
        #     model="gpt-3.5-turbo",
        #     messages=[{"role": "user", "content": prompt}],
        #     max_tokens=150,
        #     temperature=0.3
        # )
        # response_text = response.choices[0].message.content.strip()
        # 
        # # 解析结果（这里需要根据实际返回格式进行调整）
        # # 示例解析逻辑
        # emotion_type = ""
        # negative_score = 5
        # emotion_description = ""
        # 
        # for line in response_text.split('\n'):
        #     if line.startswith("1. 情绪类型："):
        #         emotion_type = line.replace("1. 情绪类型：", "").strip()
        #     elif line.startswith("2. 负面程度评分："):
        #         try:
        #             negative_score = int(line.replace("2. 负面程度评分：", "").strip())
        #         except:
        #             negative_score = 5
        #     elif line.startswith("3. 情绪描述："):
        #         emotion_description = line.replace("3. 情绪描述：", "").strip()
        
        return EmotionAnalysisResult(
            emotion_type=emotion_type,
            negative_score=negative_score,
            emotion_description=emotion_description
        )
    except Exception as e:
        # 出错时返回默认中性结果
        return EmotionAnalysisResult(
            emotion_type="中性",
            negative_score=4,
            emotion_description=f"情感分析出错: {str(e)}"
        )

# 生成回复内容的核心函数
def generate_reply(circle_content: str, reply_style: str, 
                  is_first_reply: bool, previous_replies: List[str] = None,
                  emotion_analysis: EmotionAnalysisResult = None):
    """
    调用大模型生成回复内容
    """
    try:
        # 构建提示词，加入情感分析信息
        emotion_info = ""
        if emotion_analysis:
            emotion_info = "\n朋友圈情感分析结果:\n- 情绪类型: " + emotion_analysis.emotion_type + "\n- 负面程度评分: " + str(emotion_analysis.negative_score) + "\n- 情绪描述: " + emotion_analysis.emotion_description + "\n"
            
        if is_first_reply:
            prompt = "请生成一个" + reply_style + "风格的朋友圈回复。\n"
            prompt += "朋友圈内容: " + circle_content + "\n"
            prompt += emotion_info + "\n"
            prompt += "回复要求:\n"
            prompt += "1. 回复风格必须是" + reply_style + "\n"
            prompt += "2. 回复应考虑朋友圈内容的情感状态，对于负面情绪应给予适当安慰或支持\n"
            prompt += "3. 内容限定50字以内\n"
            prompt += "4. 可以包含文字和微信表情包\n"
            prompt += "5. 内容必须符合中国法律法规\n"
            prompt += "6. 直接输出回复内容，不要添加其他解释"
        else:
            # 构建包含历史回复的提示词
            history_text = "\n之前的回复:\n"
            for i, reply in enumerate(previous_replies[-10:], 1):  # 只保留最近10条
                history_text += "%d. %s\n" % (i, reply)
            
            prompt = "请生成一个" + reply_style + "风格的朋友圈回复。\n"
            prompt += "朋友圈内容: " + circle_content + "\n"
            prompt += emotion_info + "\n"
            prompt += history_text + "\n"
            prompt += "回复要求:\n"
            prompt += "1. 回复风格必须是" + reply_style + "\n"
            prompt += "2. 回复应考虑朋友圈内容的情感状态，对于负面情绪应给予适当安慰或支持\n"
            prompt += "3. 内容限定50字以内\n"
            prompt += "4. 可以包含文字和微信表情包\n"
            prompt += "5. 内容必须符合中国法律法规\n"
            prompt += "6. 直接输出回复内容，不要添加其他解释"
        
        # 调用OpenAI API (模拟实现，实际使用时需要根据具体API调整)
        # 这里为了演示，返回模拟内容
        # 实际项目中替换为真实的API调用
        
        # 模拟回复生成，根据情感分析结果调整回复内容
        if emotion_analysis:
            # 根据情感状态生成不同的模拟回复
            if emotion_analysis.negative_score >= 6:  # 负面情绪
                mock_replies = {
                    "幽默": "希望我的回复能让你心情好一点~ 😉",
                    "严肃": "理解你的感受，一切都会好起来的。",
                    "暧昧": "很心疼你的状态，需要一个拥抱吗？ 🫂",
                    "温馨": "别难过，我在这里陪伴你~ 🌟",
                    "批评": "虽然情绪不好，但我们可以一起分析问题。"
                }
            elif emotion_analysis.negative_score <= 3:  # 积极情绪
                mock_replies = {
                    "幽默": "看到你开心我也很开心！😂",
                    "严肃": "你的积极态度很值得赞赏。",
                    "暧昧": "你的快乐感染了我~ 😊",
                    "温馨": "真好，能分享你的快乐~ 🌟",
                    "批评": "虽然整体积极，但还有些小建议想和你探讨。"
                }
            else:  # 中性情绪
                mock_replies = {
                    "幽默": "哈哈，说得太对了！😂",
                    "严肃": "你说得很有道理，值得深思。",
                    "暧昧": "这个分享很特别呢~ 😊",
                    "温馨": "看完很温暖，谢谢分享~ 🌟",
                    "批评": "我认为这个观点还有待商榷。"
                }
        else:
            # 默认回复
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
    
    # 进行情感分析
    emotion_analysis_result = analyze_emotion(request.circle_content)
    
    # 生成回复，传入情感分析结果
    reply_content = generate_reply(
        circle_content=request.circle_content,
        reply_style=request.reply_style,
        is_first_reply=first_reply,
        previous_replies=history_replies,
        emotion_analysis=emotion_analysis_result
    )
    
    # 保存新回复
    save_reply_history(request.user_id, request.post_id, reply_content)
    
    # 返回结果，包含情感分析信息
    return ReplyResponse(
        reply_content=reply_content,
        is_first_reply=first_reply,
        timestamp=datetime.now(),
        emotion_analysis=emotion_analysis_result
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

# API端点：检测广告
@app.post("/detect_ad", response_model=AdDetectionResponse)
async def detect_ad_endpoint(request: AdDetectionRequest):
    # 验证朋友圈内容
    if not request.circle_content or len(request.circle_content.strip()) == 0:
        raise HTTPException(status_code=400, detail="朋友圈内容不能为空")
    
    # 执行广告检测
    detection_result = detect_ad(request.circle_content)
    
    # 构建响应
    response_text = "我不感兴趣" if detection_result["is_ad"] else "非广告内容"
    
    return AdDetectionResponse(
        is_ad=detection_result["is_ad"],
        response_text=response_text,
        confidence=detection_result["confidence"],
        timestamp=datetime.now()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)