import requests
import json

# 测试API端点
def test_health_endpoint():
    try:
        response = requests.get("http://localhost:8000/health", timeout=10)
        print("健康检查端点响应:")
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {response.json()}")
        return True
    except Exception as e:
        print(f"健康检查失败: {str(e)}")
        return False

def test_generate_reply():
    try:
        # 测试数据
        test_data = {
            "circle_content": "今天天气真好，出去走走心情都变好了！",
            "reply_style": "幽默",
            "user_id": "test_user_123",
            "post_id": "post_456",
            "previous_replies": []
        }
        
        response = requests.post(
            "http://localhost:8000/generate_reply",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print("\n生成回复端点响应:")
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {response.json()}")
        return True
    except Exception as e:
        print(f"生成回复失败: {str(e)}")
        return False

if __name__ == "__main__":
    print("开始测试API...")
    
    # 测试健康检查端点
    health_ok = test_health_endpoint()
    
    # 测试生成回复端点
    if health_ok:
        test_generate_reply()
    
    print("\n测试完成。")