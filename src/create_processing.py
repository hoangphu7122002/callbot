from src.chatbot_client import ChatbotClient
from config.config import config
import io
from pydub import AudioSegment

def create_processing_message():
    # Khởi tạo chatbot client
    chatbot = ChatbotClient(config)
    
    # Text thông báo đang xử lý
    processing_text = "Tôi đang xử lý câu trả lời, xin vui lòng đợi trong giây lát."
    
    # Tạo audio từ text
    response = chatbot.client.audio.speech.create(
        model="tts-1",
        voice=config.TTS_OPENAI_VOICE,
        input=processing_text
    )
    
    # Chuyển đổi và lưu file
    audio_segment = AudioSegment.from_mp3(io.BytesIO(response.content))
    audio_segment.export("/home/hm1905/records/processing.wav", format='wav')

if __name__ == "__main__":
    create_processing_message() 
