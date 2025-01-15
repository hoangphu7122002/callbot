import asyncio
import time
from src.audio_handler import AudioHandler
from src.speech_processor import SpeechProcessor
from src.chatbot_client import ChatbotClient
import websockets
import json
import base64
import io
from openai import OpenAI
from config.config import config
from src.text_normalizer import TextNormalizer
import sys
import os

# Khởi tạo OpenAI client
client = OpenAI(api_key=config.OPENAI_API_KEY)

# Khởi tạo các handler với config
audio_handler = AudioHandler(
    chunk=config.AUDIO_CHUNK,
    channels=config.AUDIO_CHANNELS,
    rate=config.AUDIO_RATE,
    silence_threshold=config.SILENCE_THRESHOLD,
    silence_chunks=config.SILENCE_CHUNKS,
    initial_silence_chunks=config.INITIAL_SILENCE_CHUNKS
)
speech_processor = SpeechProcessor()
chatbot = ChatbotClient(config)

async def text_to_speech(text: str):
    try:
        if config.TTS_PROVIDER == "openai":
            # Gọi API OpenAI TTS với cú pháp mới
            # response = client.audio.speech.create(
            #     model="tts-1",
            #     voice=config.TTS_OPENAI_VOICE,
            #     input=text
            # )
            
            # # Lấy audio data
            # audio_data = io.BytesIO(response.content)
            # audio_handler.play_audio(audio_data)
            audio_handler.play_audio(text)
        else:
            async with websockets.connect(config.TTS_WEBSOCKET_URL) as websocket:
                request_data = {
                    "text": text,
                    "language": config.TTS_LANGUAGE,
                    "sample_file": config.TTS_VOICE
                }
                await websocket.send(json.dumps(request_data))
                
                while True:
                    try:
                        response = await websocket.recv()
                        data = json.loads(response)
                        
                        if "error" in data:
                            print(f"Lỗi: {data['error']}")
                            break
                            
                        if data.get("status") == "error":
                            print(f"Lỗi xử lý câu: {data.get('error')}")
                            continue
                            
                        audio_bytes = base64.b64decode(data["audio_base64"])
                        audio_handler.play_audio(audio_bytes)
                        
                        if data["index"] == data["total"] - 1:
                            break
                            
                    except websockets.exceptions.ConnectionClosed:
                        print("Kết nối WebSocket bị đóng")
                        break
                    
    except Exception as e:
        print(f"Lỗi khi xử lý text-to-speech: {e}")

async def main():
    print("Bot đang lắng nghe... (Im lặng 5 giây sẽ kết thúc)")
    text_normalizer = TextNormalizer()
    
    try:
        start_time = time.time()  # Bắt đầu đếm thời gian
        
        while True:
            # Kiểm tra thời gian
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            if elapsed_time >= config.MAX_CONVERSATION_TIME:
                print(f"\nĐã vượt quá thời gian cho phép ({config.MAX_CONVERSATION_TIME} giây)")
                print("Kết thúc cuộc hội thoại.")
                break
                
            remaining_time = config.MAX_CONVERSATION_TIME - elapsed_time
            print(f"\n============================")
            print(f"Thời gian còn lại: {int(remaining_time)} giây")
            
            audio_data = audio_handler.record_audio()
            
            if audio_data is None:
                print("Không phát hiện tiếng nói, kết thúc cuộc hội thoại.")
                break
            
            user_text = await speech_processor.speech_to_text(audio_data)
            print(f"Bạn: {user_text}")
            
            if not user_text:
                continue
            
            if chatbot.should_end_conversation(user_text):
                print("Kết thúc cuộc hội thoại.")
                break
            
            bot_response = await chatbot.get_response(user_text)
            
            # Kiểm tra marker kết thúc hội thoại
            bot_response, should_end = text_normalizer.check_end_conversation(bot_response)
            
            # Chuẩn hóa text trước khi đưa vào TTS
            normalized_response = text_normalizer.normalize_vietnamese_text(bot_response)
            normalized_response = normalized_response.replace('!','.').replace(' .','.').replace("?","").replace(" ,",",")
            normalized_response = normalized_response.replace('.',',',1)
            print(f"Bot: {normalized_response}")
            await text_to_speech(normalized_response)
            
            if should_end:
                print("Bot yêu cầu kết thúc cuộc hội thoại.")
                break
            
    except Exception as e:
        print(f"Có lỗi xảy ra: {e}")
    finally:
        print("Kết thúc chương trình")

if __name__ == "__main__":
    # Khôi phục stderr nếu cần
    # sys.stderr = stderr 
    asyncio.run(main()) 