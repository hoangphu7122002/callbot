import socket
import pyaudio
import threading
import wave
import webrtcvad
import numpy as np
from array import array
import struct
import time
from queue import Queue

class RTPHandler:
    def __init__(self, local_ip="127.0.0.1", local_port=12345,
                 remote_ip="127.0.0.1", remote_port=12346,
                 chunk_size=1024, sample_rate=24000):
        # Cấu hình âm thanh
        self.CHUNK = chunk_size
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = sample_rate
        
        # Cấu hình mạng
        self.local_ip = local_ip
        self.local_port = local_port
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        
        # Khởi tạo socket UDP
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.local_ip, self.local_port))
        print(f"Đã bind socket tại {self.local_ip}:{self.local_port}")
        
        # Khởi tạo PyAudio
        self.audio = pyaudio.PyAudio()
        
        # Khởi tạo VAD
        self.vad = webrtcvad.Vad(3)
        
        # Queue cho audio chunks
        self.audio_queue = Queue()
        
        # Flags điều khiển
        self.is_recording = False
        self.is_playing = False
        
        # RTP header fields
        self.sequence_number = 0
        self.timestamp = 0

    def create_rtp_header(self):
        """Tạo RTP header"""
        version = 2
        padding = 0
        extension = 0
        csrc_count = 0
        marker = 0
        payload_type = 0  # PCM audio
        
        first_byte = (version << 6) | (padding << 5) | (extension << 4) | csrc_count
        second_byte = (marker << 7) | payload_type
        
        header = struct.pack('!BBHII',
            first_byte,
            second_byte,
            self.sequence_number,
            self.timestamp,
            0)  # SSRC
        
        self.sequence_number = (self.sequence_number + 1) & 0xFFFF
        self.timestamp += self.CHUNK
        
        return header

    def record_audio(self):
        """Ghi âm và gửi qua RTP"""
        stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )

        print("* Đang ghi âm và gửi RTP stream...")
        frames = []
        silent_chunks = 0
        has_speech = False

        while True:
            try:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                
                # Chỉ gửi qua RTP, không phát trực tiếp
                
                if len(data) == self.CHUNK * 2:
                    
                    rtp_packet = self.create_rtp_header() + data
                    self.sock.sendto(rtp_packet, (self.remote_ip, self.remote_port))
                
                # Xử lý VAD
                array_data = array('h', data)
                volume = sum(abs(x) for x in array_data) / len(array_data)

                if volume > 300:
                    silent_chunks = 0
                    has_speech = True
                    frames.append(data)
                else:
                    silent_chunks += 1
                    if has_speech:
                        frames.append(data)

                if has_speech and silent_chunks > 60:
                    break
                elif not has_speech and silent_chunks > 80:
                    stream.stop_stream()
                    stream.close()
                    return None

            except Exception as e:
                print(f"Lỗi khi ghi âm: {e}")
                break

        stream.stop_stream()
        stream.close()

        if has_speech and len(frames) > 0:
            return b''.join(frames)
        return None

    def send_audio(self, audio_data):
        """Chỉ gửi audio qua RTP, không phát trực tiếp"""
        if not audio_data:
            return
            
        try:
            # Chia audio thành các chunk và gửi qua RTP
            for i in range(0, len(audio_data), self.CHUNK):
                chunk = audio_data[i:i + self.CHUNK]
                if len(chunk) == self.CHUNK:
                    rtp_packet = self.create_rtp_header() + chunk
                    self.sock.sendto(rtp_packet, (self.remote_ip, self.remote_port))
                    time.sleep(0.02)  # Delay giữa các chunk
            
        except Exception as e:
            print(f"Lỗi khi gửi audio: {str(e)}")

    def stop(self):
        """Dừng tất cả hoạt động"""
        self.is_recording = False
        self.is_playing = False
        
        try:
            self.audio.terminate()
        except:
            pass
            
        try:
            self.sock.close()
        except:
            pass
        
        print("Đã dừng RTP handler") 