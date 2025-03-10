from src.chatbot_client import ChatbotClient
from config.config import config
import io
from pydub import AudioSegment

def create_welcome_message():
    # Khởi tạo chatbot client
    chatbot = ChatbotClient(config)
    
    # Text chào mừng
    welcome_text = "kính chào anh chị, đây là cuộc gọi được thực hiện bởi callbot của trung tâm dịch vụ phân tích dữ liệu vê tê ét Nhân dịp năm mới, thay mặt phòng ây ai kính chúc anh chị 1 năm mới an khang thịnh vượng, anh chị có lời nhắn gửi gì cho phòng ây ai không ạ."
    
    # Tạo audio từ text
    response = chatbot.client.audio.speech.create(
        model="tts-1",
        voice=config.TTS_OPENAI_VOICE,
        input=welcome_text
    )
    
    # Chuyển đổi và lưu file
    audio_segment = AudioSegment.from_mp3(io.BytesIO(response.content))
    audio_segment.export("/home/hm1905/records/welcome_trung.wav", format='wav')

if __name__ == "__main__":
    create_welcome_message() 
