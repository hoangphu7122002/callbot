import pyaudio
import asyncio
import time
from src.rtp_handler import RTPHandler
from src.speech_processor import SpeechProcessor
from src.chatbot_client import ChatbotClient
from config.config import config
from src.text_normalizer import TextNormalizer
import io
from queue import Queue
import threading

class CallbotRTPDemo:
    def __init__(self):
        # Khởi tạo RTP Handler cho stream audio
        self.rtp_handler = RTPHandler(
            local_ip="0.0.0.0",  # Lắng nghe tất cả các interface
            local_port=5004,      # Port chuẩn cho RTP
            remote_ip="127.0.0.1",
            remote_port=5006      # Port để gửi đến VLC
        )
        
        # Khởi tạo các component của callbot
        self.speech_processor = SpeechProcessor()
        self.chatbot = ChatbotClient(config)
        self.text_normalizer = TextNormalizer()
        
        # Buffer để lưu audio data
        self.audio_buffer = b''
        self.buffer_lock = threading.Lock()
        
        # Cờ điều khiển
        self.is_running = False

    async def process_audio(self):
        """Xử lý audio buffer và tương tác với chatbot"""
        while self.is_running:
            try:
                with self.buffer_lock:
                    if len(self.audio_buffer) > 32000:  # Khoảng 2 giây audio
                        # Chuyển audio thành text
                        user_text = await self.speech_processor.speech_to_text(self.audio_buffer)
                        self.audio_buffer = b''  # Reset buffer
                        
                        if user_text:
                            print(f"User: {user_text}")
                            
                            # Lấy phản hồi từ chatbot
                            bot_response = await self.chatbot.get_response(user_text)
                            
                            # Chuẩn hóa phản hồi
                            bot_response, should_end = self.text_normalizer.check_end_conversation(bot_response)
                            normalized_response = self.text_normalizer.normalize_vietnamese_text(bot_response)
                            print(f"Bot: {normalized_response}")
                            
                            # Gửi phản hồi qua RTP stream
                            # Ở đây bạn có thể sử dụng OpenAI TTS hoặc local TTS
                            # Ví dụ với OpenAI TTS:
                            response = self.chatbot.client.audio.speech.create(
                                model="tts-1",
                                voice="alloy",
                                input=normalized_response
                            )
                            
                            # Gửi audio qua RTP
                            audio_data = response.content
                            # Chia nhỏ audio thành các chunk và gửi
                            chunk_size = 960  # Kích thước phù hợp với RTP
                            for i in range(0, len(audio_data), chunk_size):
                                chunk = audio_data[i:i + chunk_size]
                                if len(chunk) == chunk_size:  # Chỉ gửi chunk đủ kích thước
                                    self.rtp_handler.sock.sendto(
                                        self.rtp_handler.create_rtp_header() + chunk,
                                        (self.rtp_handler.remote_ip, self.rtp_handler.remote_port)
                                    )
                                    await asyncio.sleep(0.02)  # Đợi một chút giữa các chunk
                            
                            if should_end:
                                print("Bot yêu cầu kết thúc cuộc hội thoại.")
                                self.stop()
                                break
                
                await asyncio.sleep(0.1)  # Tránh CPU quá tải
                
            except Exception as e:
                print(f"Lỗi khi xử lý audio: {e}")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback để nhận audio data từ microphone"""
        if self.is_running:
            with self.buffer_lock:
                self.audio_buffer += in_data
        return (in_data, pyaudio.paContinue)

    def start(self):
        """Bắt đầu demo"""
        print("\nBắt đầu CallBot RTP Demo...")
        print("Để phát audio stream trong VLC:")
        print(f"vlc rtp://@:{self.rtp_handler.local_port}")
        print("hoặc")
        print(f"ffplay rtp://127.0.0.1:{self.rtp_handler.local_port}")
        
        self.is_running = True
        
        # Bắt đầu ghi âm với callback
        self.rtp_handler.start_recording()
        
        # Chạy audio processor trong event loop
        asyncio.run(self.process_audio())

    def stop(self):
        """Dừng demo"""
        self.is_running = False
        self.rtp_handler.stop()
        print("\nĐã dừng demo")

def main():
    demo = CallbotRTPDemo()
    try:
        demo.start()
    except KeyboardInterrupt:
        print("\nNhận tín hiệu dừng...")
    finally:
        demo.stop()

if __name__ == "__main__":
    main() 