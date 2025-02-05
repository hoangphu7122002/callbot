import requests

# Định nghĩa URL API
url = "http://34.46.101.40:8088/v1/chat-messages"

# Định nghĩa headers
headers = {
    "Authorization": "Bearer app-T6Vb0gMXUYVGU1puhd8f6FyS",
    "Content-Type": "application/json"
}

# Định nghĩa payload (dữ liệu gửi đi)
data = {
    "inputs": {},
    "query": "What are the specs of the iPhone 13 Pro Max?",
    "response_mode": "streaming",
    "conversation_id": "",
    "user": "abc-123",
    "files": [
        {
            "type": "image",
            "transfer_method": "remote_url",
            "url": "https://cloud.dify.ai/logo/logo-site.png"
        }
    ]
}

# Gửi yêu cầu POST
response = requests.post(url, headers=headers, json=data)

# In kết quả phản hồi từ server
print("Status Code:", response.status_code)
print("Response:", response.text)
