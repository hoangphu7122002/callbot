from src.chatbot_client import ChatbotClient
from config.config import config
import io
from pydub import AudioSegment

def create_welcome_message():
    # Khởi tạo chatbot client
    chatbot = ChatbotClient(config)
    
    # Text chào mừng
    welcome_text = "Chào anh chị! tôi là trợ lý tư vấn của VCBS. Tôi ở đây để hỗ trợ bạn về các thủ tục chuyển tiền và mở tài khoản. Nếu anh chị có bất kỳ câu hỏi nào liên quan đến các dịch vụ của chúng tôi, hãy thoải mái hỏi nhé!"
    
    # Tạo audio từ text
    response = chatbot.client.audio.speech.create(
        model="tts-1",
        voice=config.TTS_OPENAI_VOICE,
        input=welcome_text
    )
    
    # Chuyển đổi và lưu file
    audio_segment = AudioSegment.from_mp3(io.BytesIO(response.content))
    audio_segment.export("/home/hm1905/records/welcome_vcbs.wav", format='wav')

if __name__ == "__main__":
    create_welcome_message()
