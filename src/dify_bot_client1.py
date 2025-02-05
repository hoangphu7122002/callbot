import requests
import json

class DifyBotClient:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        self.conversation_id = None

    def get_response(self, query, user_id="default-user"):
        payload = {
            "inputs": {},
            "query": query,
            "response_mode": "blocking",
            "conversation_id": "" if self.conversation_id is None else self.conversation_id,
            "user": user_id,
            "files": []
        }

        # Chỉ thêm conversation_id vào payload nếu đã có
        if self.conversation_id:
            payload["conversation_id"] = self.conversation_id

        try:
            print(payload)
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            response_data = response.json()
            
            # Lấy conversation_id từ response
            if 'conversation_id' in response_data:
                self.conversation_id = response_data['conversation_id']
            
            return response_data.get('answer', '')
            
        except Exception as e:
            print(f"Error calling Dify API: {str(e)}")
            return "Sorry, I encountered an error while processing your request."

    def end_conversation(self, user_id="default-user"):
        """Kết thúc và xóa conversation"""
        if not self.conversation_id:
            return
            
        try:
            url = f"{self.api_url.rsplit('/', 1)[0]}/conversations/{self.conversation_id}"
            payload = {
                "user": user_id
            }
            response = requests.delete(url, headers=self.headers, json=payload)
            response.raise_for_status()
            self.conversation_id = None
            print("end conversation done")
            
        except Exception as e:
            print(f"Error ending conversation: {str(e)}")

    def reset_conversation(self):
        """Reset conversation bằng cách xóa conversation_id"""
        self.conversation_id = None 
