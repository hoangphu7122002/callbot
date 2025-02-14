import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Endpoints
    TTS_WEBSOCKET_URL = "ws://t2s.vts-dasc.net/ws/generate_speech/"
    STT_API_URL = "https://asr.vts-dasc.net/asr/upload/?en=false"

    # Audio Settings
    AUDIO_CHUNK = 1024
    AUDIO_FORMAT = "paInt16" #8
    AUDIO_CHANNELS = 1
    AUDIO_RATE = 8000
    SILENCE_THRESHOLD = 300 # Giảm ngưỡng để nhạy hơn với âm thanh
    SILENCE_CHUNKS = 60# Số chunk im lặng để dừng khi đã phát hiện tiếng nói (khoảng 2s thì dừng)
    INITIAL_SILENCE_CHUNKS = 80 # Thời gian chờ ban đầu (khoảng 3-4s thì dừng)
    MAX_CONVERSATION_TIME = 300 # Thời gian tối đa cho mỗi cuộc trò chuyện (khoảng 5 phút)

    # Text-to-Speech Settings
    # TTS_PROVIDER = "openai" #local
    TTS_PROVIDER = "local"
    TTS_VOICE = "nam-calm.wav"
    TTS_OPENAI_VOICE = "alloy"
    TTS_LANGUAGE = "vi"

    # Speech-to-Text Settings
    # STT_PROVIDER = "openai" #local
    STT_PROVIDER = "local"
    STT_LANGUAGE = "vi"
    STT_MODEL = "whisper-1"

    # Chatbot Settings
    END_CONVERSATION_KEYWORDS = ["tạm biệt", "goodbye", "bye", "kết thúc"]
    
    # OpenAI config
    GPT_MODEL = 'gpt-4o-mini'  # hoặc model bạn đang sử dụng
    OPENAI_API_KEY = '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'
    # Dify config
    DIFY_API_URL = "http://34.174.214.130:8088/v1/chat-messages"
    DIFY_API_KEY = "app-jEAZXlZZVZpdpximRcwqKafz"

    # Add bot type configuration
    BOT_TYPE = "dify"  # or "chatgpt" for switching between bots
    
    # BOT_TYPE = "chatgpt"  # or "chatgpt" for switching between bots

    # RTP Settings
    RTP_LOCAL_IP = "127.0.0.1"     # Localhost
    # RTP_LOCAL_IP = "34.29.227.22"

    
    # Port settings
    USER_PORT = 5060               # Port user gửi/nhận
    BOT_PORT = 5006               # Port bot gửi/nhận
    
    # Audio settings
    # AUDIO_CHUNK = 1024            # Chunk size phải giống nhau
    # AUDIO_RATE = 24000            # Sample rate phải giống nhau
    # AUDIO_CHANNELS = 1
     # SILENCE_THRESHOLD = 300

# Create a singleton instance
config = Config()
