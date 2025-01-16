import asyncio
import threading
import pyaudio
from src.rtp_handler import RTPHandler
from src.speech_processor import SpeechProcessor
from src.chatbot_client import ChatbotClient
from src.text_normalizer import TextNormalizer
from config.config import config
from pydub import AudioSegment
import io
import wave
import socket

class RTPBot:
    def __init__(self):
        # Khởi tạo RTP Handler cho bot
        self.rtp_handler = RTPHandler(
            local_ip=config.RTP_LOCAL_IP,
            local_port=config.BOT_PORT,      # Bot lắng nghe ở 5006
            remote_ip=config.RTP_LOCAL_IP,
            remote_port=config.USER_PORT,    # Bot gửi đến 5002
            chunk_size=config.AUDIO_CHUNK,
            sample_rate=config.AUDIO_RATE
        )
        
        # Khởi tạo các components
        self.speech_processor = SpeechProcessor()
        self.chatbot = ChatbotClient(config)
        self.text_normalizer = TextNormalizer()
        self.audio = pyaudio.PyAudio()
        self.is_running = True
        
        # Buffer cho audio đang nhận
        self.current_audio = []
        self.is_receiving = False
        self.silence_count = 0

    async def process_audio(self, audio_data):
        """Xử lý audio và tạo phản hồi"""
        try:
            # Chuyển audio thành text
            user_text = await self.speech_processor.speech_to_text(audio_data)
            if not user_text:
                return
                
            print(f"User: {user_text}")
            
            # Lấy phản hồi từ chatbot
            bot_response = await self.chatbot.get_response(user_text)
            bot_response, _ = self.text_normalizer.check_end_conversation(bot_response)
            normalized_response = self.text_normalizer.normalize_vietnamese_text(bot_response)
            print(f"Bot: {normalized_response}")
            
            # Chuyển text thành speech
            response = self.chatbot.client.audio.speech.create(
                model="tts-1",
                voice=config.TTS_OPENAI_VOICE,
                input=normalized_response
            )
            
            # Chuyển MP3 thành WAV
            audio_segment = AudioSegment.from_mp3(io.BytesIO(response.content))
            wav_io = io.BytesIO()
            audio_segment.export(wav_io, format='wav')
            wav_io.seek(0)
            
            with wave.open(wav_io, 'rb') as wav_file:
                wav_data = wav_file.readframes(wav_file.getnframes())
            
            # Gửi phản hồi qua RTP
            self.rtp_handler.send_audio(wav_data)
            
        except Exception as e:
            print(f"Lỗi khi xử lý audio: {e}")

    async def run(self):
        """Chạy bot"""
        print("\nBot đang lắng nghe...")
        buffer = []
        silence_count = 0
        
        while self.is_running:
            try:
                data, _ = self.rtp_handler.sock.recvfrom(2060)
                audio_data = data[12:]  # Bỏ RTP header
                # print("--------------")
                # print("audio_data",len(audio_data))
                # print("config.AUDIO_CHUNK",config.AUDIO_CHUNK)
                # print("--------------")
                if len(audio_data) == config.AUDIO_CHUNK * 2:
                    # Kiểm tra âm lượng
                    volume = max(abs(int.from_bytes(audio_data[i:i+2], 'little', signed=True)) 
                               for i in range(0, len(audio_data), 2))
                    
                    if volume > 300:  # Có tiếng nói
                        silence_count = 0
                        buffer.append(audio_data)
                    else:
                        silence_count += 1
                        if buffer:  # Đã có tiếng nói trước đó
                            buffer.append(audio_data)
                    
                    # Xử lý khi đủ độ im lặng
                    if silence_count > 60 and buffer:  # ~2s im lặng
                        await self.process_audio(b''.join(buffer))
                        buffer = []
                        silence_count = 0
                        
            except Exception as e:
                if self.is_running:
                    print(f"Lỗi: {e}")

    def start(self):
        """Khởi động bot"""
        print("\nKhởi động Callbot...")
        print("Đang kết nối với VLC và user...")
        print("Nhấn Ctrl+C để dừng")
        
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            print("\nĐang dừng...")
        finally:
            self.is_running = False
            self.rtp_handler.stop()

if __name__ == "__main__":
    bot = RTPBot()
    bot.start() 