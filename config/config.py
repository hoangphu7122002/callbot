class Config:
    # API Endpoints
    TTS_WEBSOCKET_URL = "ws://localhost:38001/ws/generate_speech/"
    STT_API_URL = "http://localhost:38000/asr/upload/?en=false"

    # Audio Settings
    AUDIO_CHUNK = 1024
    AUDIO_FORMAT = "paInt16"
    AUDIO_CHANNELS = 1
    AUDIO_RATE = 24000
    SILENCE_THRESHOLD = 300 # Giảm ngưỡng để nhạy hơn với âm thanh
    SILENCE_CHUNKS = 60# Số chunk im lặng để dừng khi đã phát hiện tiếng nói (khoảng 2s thì dừng)
    INITIAL_SILENCE_CHUNKS = 80 # Thời gian chờ ban đầu (khoảng 3-4s thì dừng)
    MAX_CONVERSATION_TIME = 300 # Thời gian tối đa cho mỗi cuộc trò chuyện (khoảng 5 phút)

    # Text-to-Speech Settings
    TTS_PROVIDER = "openai" #local
    # TTS_VOICE = "nu-calm.wav"
    TTS_OPENAI_VOICE = "alloy"
    TTS_LANGUAGE = "vi"

    # Speech-to-Text Settings
    STT_PROVIDER = "openai" #local
    STT_LANGUAGE = "vi"
    STT_MODEL = "whisper-1"

    # Chatbot Settings
    END_CONVERSATION_KEYWORDS = ["tạm biệt", "goodbye", "bye", "kết thúc"]
    
    # OpenAI config
    GPT_MODEL = 'gpt-4o-mini'  # hoặc model bạn đang sử dụng
    OPENAI_API_KEY = 'key'

    # Dify config
    DIFY_API_URL = "http://127.0.0.1:25001/v1/chat-messages"
    DIFY_API_KEY = "app-36WvU65NrwXoMOl9bkwb23yG"

    # Add bot type configuration
    # BOT_TYPE = "dify"  # or "chatgpt" for switching between bots
    
    BOT_TYPE = "chatgpt"  # or "chatgpt" for switching between bots

# Create a singleton instance
config = Config()