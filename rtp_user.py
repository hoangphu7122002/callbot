import asyncio
import threading
import pyaudio
import socket
from src.rtp_handler import RTPHandler
from config.config import config

class RTPUser:
    def __init__(self):
        # Khởi tạo RTP Handler cho user
        self.rtp_handler = RTPHandler(
            local_ip=config.RTP_LOCAL_IP,
            local_port=config.USER_PORT,     # User lắng nghe ở 5002
            remote_ip=config.RTP_LOCAL_IP,
            remote_port=config.BOT_PORT,     # User gửi đến 5006
            chunk_size=config.AUDIO_CHUNK,
            sample_rate=config.AUDIO_RATE
        )
        
        # Khởi tạo PyAudio
        self.audio = pyaudio.PyAudio()
        self.is_running = True
        
        # Thread nhận audio từ bot
        self.receive_thread = threading.Thread(target=self._receive_audio, daemon=True)
        self.receive_thread.start()

    def _receive_audio(self):
        """Nhận và phát audio từ bot"""
        stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=config.AUDIO_RATE,
            output=True,
            frames_per_buffer=config.AUDIO_CHUNK
        )
        
        print("Đang lắng nghe phản hồi từ bot...")
        
        while self.is_running:
            try:
                data, _ = self.rtp_handler.sock.recvfrom(2048)
                audio_data = data[12:]  # Bỏ RTP header
                if len(audio_data) == config.AUDIO_CHUNK:
                    stream.write(audio_data)
            except Exception as e:
                if self.is_running:
                    print(f"Lỗi khi nhận audio: {e}")
        
        stream.close()

    def start(self):
        """Bắt đầu ghi âm và gửi"""
        print("\nBắt đầu phiên người dùng...")
        print("Đang kết nối với VLC và bot...")
        print("Nhấn Ctrl+C để dừng")
        
        try:
            while True:
                # Ghi âm và gửi qua RTP
                audio_data = self.rtp_handler.record_audio()
                if audio_data is None:
                    print("Không phát hiện tiếng nói, thử lại...")
                    continue
                
        except KeyboardInterrupt:
            print("\nĐang dừng...")
        finally:
            self.is_running = False
            self.rtp_handler.stop()

if __name__ == "__main__":
    user = RTPUser()
    user.start() 