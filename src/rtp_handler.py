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
    def __init__(self, local_ip="0.0.0.0", local_port=12345,
                 remote_ip="127.0.0.1", remote_port=12346,
                 chunk_size=960, sample_rate=16000):
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
        
        # Khởi tạo PyAudio
        self.audio = pyaudio.PyAudio()
        
        # Khởi tạo VAD
        self.vad = webrtcvad.Vad(3)  # Aggressiveness level 3
        
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
            0)  # SSRC (synchronization source)
        
        self.sequence_number = (self.sequence_number + 1) & 0xFFFF
        self.timestamp += self.CHUNK
        
        return header

    def start_recording(self):
        """Bắt đầu ghi âm và gửi RTP"""
        self.is_recording = True
        self.recording_stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )
        
        threading.Thread(target=self._record_and_send).start()

    def _record_and_send(self):
        """Thread ghi âm và gửi RTP"""
        while self.is_recording:
            try:
                audio_data = self.recording_stream.read(self.CHUNK)
                # Kiểm tra VAD
                if self.vad.is_speech(audio_data, self.RATE):
                    # Tạo và gửi gói RTP
                    rtp_packet = self.create_rtp_header() + audio_data
                    self.sock.sendto(rtp_packet, (self.remote_ip, self.remote_port))
            except Exception as e:
                print(f"Lỗi khi ghi âm và gửi RTP: {e}")

    def start_playing(self):
        """Bắt đầu nhận và phát RTP"""
        self.is_playing = True
        self.playback_stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            output=True,
            frames_per_buffer=self.CHUNK
        )
        
        threading.Thread(target=self._receive_and_play).start()

    def _receive_and_play(self):
        """Thread nhận và phát RTP"""
        while self.is_playing:
            try:
                data, addr = self.sock.recvfrom(2048)
                # Bỏ qua RTP header (12 bytes)
                audio_data = data[12:]
                self.playback_stream.write(audio_data)
            except Exception as e:
                print(f"Lỗi khi nhận và phát RTP: {e}")

    def stop(self):
        """Dừng tất cả hoạt động"""
        self.is_recording = False
        self.is_playing = False
        
        if hasattr(self, 'recording_stream'):
            self.recording_stream.stop_stream()
            self.recording_stream.close()
            
        if hasattr(self, 'playback_stream'):
            self.playback_stream.stop_stream()
            self.playback_stream.close()
            
        self.audio.terminate()
        self.sock.close() 