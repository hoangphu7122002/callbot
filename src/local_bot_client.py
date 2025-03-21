import aiohttp
import logging

class LocalBotClient:
    def __init__(self, api_url):
        self.api_url = api_url
        self.conversation_id = 0

    async def get_response(self, message):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json={
                        "conversation_id": self.conversation_id,
                        "content": message,
                        "collection": "general"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["bot_response"]
                    else:
                        logging.error(f"Error from local LLM API: {response.status}")
                        return "Xin lỗi, tôi đang gặp sự cố kỹ thuật."
        except Exception as e:
            logging.error(f"Error calling local LLM API: {e}")
            return "Xin lỗi, tôi đang gặp sự cố kỹ thuật."

    def end_conversation(self):
        self.conversation_id = 0 