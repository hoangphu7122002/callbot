import requests
import json
import uuid

class DifyBotClient:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        # Tạo conversation_id mới khi khởi tạo bot
        self.conversation_id = str(uuid.uuid4())

    async def get_response(self, query, user_id="default-user"):
        payload = {
            "inputs": {},
            "query": query,
            "response_mode": "blocking",
            "conversation_id": self.conversation_id,  # Sử dụng conversation_id đã tạo
            "user": user_id,
            "files": []
        }

        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            response_data = response.json()
            
            # Cập nhật conversation_id từ response nếu có
            if 'conversation_id' in response_data:
                self.conversation_id = response_data['conversation_id']
            
            return response_data.get('answer', '')
            
        except Exception as e:
            print(f"Error calling Dify API: {str(e)}")
            return "Sorry, I encountered an error while processing your request."

    def reset_conversation(self):
        """Reset conversation bằng cách tạo conversation_id mới"""
        self.conversation_id = str(uuid.uuid4()) 