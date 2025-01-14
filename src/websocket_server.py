import asyncio
import websockets
from .audio_handler import AudioHandler
from .speech_processor import SpeechProcessor
from .chatbot_client import ChatbotClient
from config.config import config

class CallbotServer:
    def __init__(self):
        self.audio_handler = AudioHandler()
        self.speech_processor = SpeechProcessor()
        self.chatbot_client = ChatbotClient()
        
    async def handle_conversation(self, websocket):
        try:
            while True:
                # Ghi âm từ microphone
                audio_data = self.audio_handler.record_audio()
                
                # Chuyển đổi speech to text
                user_text = await self.speech_processor.speech_to_text(audio_data)
                
                # Kiểm tra nếu người dùng muốn kết thúc
                if self.chatbot_client.should_end_conversation(user_text):
                    break
                
                # Lấy phản hồi từ chatbot
                bot_response = await self.chatbot_client.get_response(user_text)
                
                # Chuyển đổi text to speech
                audio_response = await self.speech_processor.text_to_speech(bot_response)
                
                # Phát âm thanh
                self.audio_handler.play_audio(audio_response)
                
        except Exception as e:
            print(f"Error in conversation: {e}") 