from src.chatbot_client import ChatbotClient
from config.config import config
import io
from pydub import AudioSegment

def create_welcome_message():
    # Khởi tạo chatbot client
    chatbot = ChatbotClient(config)
    
    # Text chào mừng
    welcome_text = "Nếu một con tàu di chuyển với tốc độ 60 km/h và gặp một cơn gió thổi ngược với vận tốc 20 km/h, vận tốc thực tế của tàu sẽ thay đổi như thế nào?"
    
    # Tạo audio từ text
    response = chatbot.client.audio.speech.create(
        model="tts-1",
        voice=config.TTS_OPENAI_VOICE,
        input=welcome_text
    )
    
    # Chuyển đổi và lưu file
    audio_segment = AudioSegment.from_mp3(io.BytesIO(response.content))
    audio_segment.export("/home/hm1905/records/welcome5.wav", format='wav')

if __name__ == "__main__":
    create_welcome_message() 
