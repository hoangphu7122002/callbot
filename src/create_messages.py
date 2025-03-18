import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from chatbot_client import ChatbotClient
import io
from pydub import AudioSegment
from dotenv import load_dotenv

# Setup paths and environment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
dotenv_path = os.path.join(ROOT_DIR, ".env")
load_dotenv(dotenv_path)

# Default output directory - can be overridden in .env file
OUTPUT_DIR = os.getenv("AUDIO_OUTPUT_DIR", "/home/hm1905/records")

# Define message templates
MESSAGE_TEMPLATES = {
    "chao": {
        "text": "Nếu một con tàu di chuyển với tốc độ 60 km/h và gặp một cơn gió thổi ngược với vận tốc 20 km/h, vận tốc thực tế của tàu sẽ thay đổi như thế nào?",
        "filename": "welcome5.wav"
    },
    "welcome": {
        "text": "kính chào anh chị, đây là cuộc gọi được thực hiện bởi callbot của trung tâm dịch vụ phân tích dữ liệu vê tê ét Nhân dịp năm mới, thay mặt phòng ây ai kính chúc anh chị 1 năm mới an khang thịnh vượng, anh chị có lời nhắn gửi gì cho phòng ây ai không ạ.",
        "filename": "welcome_trung.wav"
    },
    "goodbye": {
        "text": "cảm ơn anh chị đã sử dụng dịch vụ tạm biệt ạ",
        "filename": "goodbye_trung.wav"
    },
    "processing": {
        "text": "Tôi đang xử lý câu trả lời, xin vui lòng đợi trong giây lát.",
        "filename": "processing.wav"
    },
    "vcbs_welcome": {
        "text": "Chào anh chị! tôi là trợ lý tư vấn của VCBS. Tôi ở đây để hỗ trợ bạn về các thủ tục chuyển tiền và mở tài khoản. Nếu anh chị có bất kỳ câu hỏi nào liên quan đến các dịch vụ của chúng tôi, hãy thoải mái hỏi nhé!",
        "filename": "welcome_vcbs.wav"
    }
}

def create_audio_message(text, output_filename, voice=None):
    """
    Core function to create an audio message from text.
    """
    try:
        # Use the voice from parameters or fall back to environment variable
        tts_voice = voice or os.getenv("TTS_OPENAI_VOICE")
        if not tts_voice:
            raise ValueError("No voice specified and TTS_OPENAI_VOICE not set in .env")
            
        # Initialize chatbot client
        chatbot = ChatbotClient()
        
        # Generate audio from text
        response = chatbot.client.audio.speech.create(
            model="tts-1",
            voice=tts_voice,
            input=text
        )
        
        # Ensure output directory exists
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Convert and save file
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        audio_segment = AudioSegment.from_mp3(io.BytesIO(response.content))
        audio_segment.export(output_path, format='wav')
        
        print(f"Created audio file: {output_path}")
        return True
        
    except Exception as e:
        print(f"Error creating audio: {str(e)}")
        return False

# Individual message creation functions for backward compatibility

def create_chao_message():
    """Creates the chao message."""
    template = MESSAGE_TEMPLATES["chao"]
    return create_audio_message(template["text"], template["filename"])

def create_welcome_message():
    """Creates the welcome message."""
    template = MESSAGE_TEMPLATES["welcome"]
    return create_audio_message(template["text"], template["filename"])

def create_goodbye_message():
    """Creates the goodbye message."""
    template = MESSAGE_TEMPLATES["goodbye"]
    return create_audio_message(template["text"], template["filename"])

def create_processing_message():
    """Creates the processing message."""
    template = MESSAGE_TEMPLATES["processing"]
    return create_audio_message(template["text"], template["filename"])

def create_vcbs_welcome_message():
    """Creates the VCBS welcome message."""
    template = MESSAGE_TEMPLATES["vcbs_welcome"]
    return create_audio_message(template["text"], template["filename"])

def create_custom_message(text, filename, voice=None):
    """Creates a custom audio message."""
    return create_audio_message(text, filename, voice)

def create_all_messages():
    """Creates all predefined messages."""
    success_count = 0
    for message_type, template in MESSAGE_TEMPLATES.items():
        print(f"Creating {message_type} message...")
        if create_audio_message(template["text"], template["filename"]):
            success_count += 1
    
    print(f"Created {success_count}/{len(MESSAGE_TEMPLATES)} messages")
    return success_count == len(MESSAGE_TEMPLATES)

if __name__ == "__main__":
    # Default behavior: create chao message
    create_chao_message()