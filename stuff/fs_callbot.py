
import asyncio
import threading
import pyaudio
import wave
import socket
import io
from freeswitchESL import ESL
from pydub import AudioSegment
from pydub.utils import which
import audioop
from src.speech_processor import SpeechProcessor
from src.chatbot_client import ChatbotClient
from src.text_normalizer import TextNormalizer
from config.config import config
from threading import Event
import time

AudioSegment.converter = which("ffmpeg")

class FSCallBot:
    def __init__(self):
        # Khởi tạo các components
        self.speech_processor = SpeechProcessor()
        self.chatbot = ChatbotClient(config)
        self.text_normalizer = TextNormalizer()
        self.playback_event = Event()
        self.active_calls = {}
        self.is_running = True
        
        # ESL connection
        self.esl_con = ESL.ESLconnection("127.0.0.1", "8021", "ClueCon")
        if not self.esl_con.connected():
            raise Exception("Failed to connect to FreeSWITCH")

    def decode_pcmu_to_pcm16(self, pcmu_data):
        """Giải mã dữ liệu PCMU (G.711u) sang PCM 16-bit."""
        return audioop.alaw2lin(pcmu_data, 2)

    def process_audio(self, audio_data, uuid):
        """Xử lý audio và tạo phản hồi"""
        try:
            # Chuyển audio thành text
            #user_text = self.speech_processor.speech_to_text(audio_data)
            processing_file = "/home/hm1905/records/processing.wav"
            self.playback_event.set()
            self.esl_con.execute("playback", processing_file, uuid)

            a = time.time()
            user_text = asyncio.run(self.speech_processor.speech_to_text(audio_data))
            b = time.time()
            print("speech to text: ", b - a)
            if not user_text:
                return
                
            print(f"User {uuid}: {user_text}")
            
            # Lấy phản hồi từ chatbot
            #bot_response = self.chatbot.get_response(user_text)
            a = time.time()
            bot_response = asyncio.run(self.chatbot.get_response(user_text))
            bot_response, _ = self.text_normalizer.check_end_conversation(bot_response)
            normalized_response = self.text_normalizer.normalize_vietnamese_text(bot_response)
            b = time.time()
            print("llm answer: ", b - a)
            print(f"Bot response to {uuid}: {normalized_response}")
            a = time.time()
            # Chuyển text thành speech
            response = self.chatbot.client.audio.speech.create(
                model="tts-1",
                voice=config.TTS_OPENAI_VOICE,
                input=normalized_response
            )
            b = time.time()
            print("text to speech: ",b - a)
            
            # Lưu file response theo UUID
            output_file = f"/home/hm1905/records/response_{uuid}.wav"
            
            # Chuyển MP3 thành WAV và lưu
            a = time.time()
            audio_segment = AudioSegment.from_mp3(io.BytesIO(response.content))
            audio_segment.export(output_file, format='wav')
            # print("done")
            b = time.time()
            print("save file text to speech time: ",b - a)
            
            # Đánh dấu đang playback
            self.playback_event.set()
            print("here")
            # Play response qua FreeSWITCH
            a = time.time()
            # self.esl_con.execute("uuid_setvar", f"{uuid} playback_terminators none")
            self.esl_con.execute("playback", output_file, uuid)
            # print("here1")
            
            # Đợi 100ms để đảm bảo playback đã bắt đầu
            # await asyncio.sleep(0.1)
            
            # Tính thời gian playback dựa trên độ dài audio
            audio_duration = len(audio_segment) / 1000.0  # Chuyển từ ms sang giây
            print("audio_duration: ",audio_duration)
            time.sleep(audio_duration)
            # print(audio_duration)
            #await asyncio.sleep(audio_duration)
            
            # Đánh dấu playback đã xong
            self.playback_event.clear()
            b = time.time()
            print("playback done time: ",b - a)
            
        except Exception as e:
            print(f"Lỗi khi xử lý audio: {e}")
            self.playback_event.clear()

    def handle_rtp_stream(self, port, uuid):
        """Xử lý luồng RTP cho mỗi cuộc gọi"""
        self.play_welcome_message(uuid)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("10.128.0.7", port))
        
        buffer = []
        silence_count = 0
        
        while self.is_running and uuid in self.active_calls:
            try:
                # Kiểm tra nếu đang playback thì bỏ qua việc đọc socket
                if self.playback_event.is_set():
                    continue
                    
                # Set timeout cho socket để có thể check playback_event thường xuyên
                sock.settimeout(0.1)
                try:
                    data, _ = sock.recvfrom(1024)
                except socket.timeout:
                    continue
                
                if not data:
                    continue
                
                # Tách phần payload RTP
                audio_data = data[12:]  # Bỏ RTP header
                
                # Kiểm tra âm lượng
                pcm_data = self.decode_pcmu_to_pcm16(audio_data)
                volume = max(abs(int.from_bytes(pcm_data[i:i+2], 'little', signed=True)) 
                           for i in range(0, len(pcm_data), 2))
                
                if volume > 300:  # Có tiếng nói
                    silence_count = 0
                    print("pcm_data",pcm_data)
                    buffer.append(pcm_data)
                else:
                    silence_count += 1
                    if buffer:
                        buffer.append(pcm_data)
                
                # Xử lý khi đủ độ im lặng
                if silence_count > 60 and buffer:  # ~2s im lặng
                    audio_data = b''.join(buffer)
                    self.process_audio(audio_data, uuid)
                    buffer = []
                    print("here")
                    silence_count = 0
                    
            except Exception as e:
                print(f"Lỗi trong handle_rtp_stream: {e}")
        
        sock.close()

    def play_welcome_message(self, uuid):
        """Phát thông điệp chào mừng"""
        welcome_file = "/home/hm1905/records/welcome.wav"
        
        # Đánh dấu đang playback
        self.playback_event.set()
        
        # Play welcome message
        self.esl_con.execute("playback", welcome_file, uuid)
        
        # Tính thời gian của file welcome
        audio = AudioSegment.from_wav(welcome_file)
        audio_duration = len(audio) / 1000.0  # Chuyển từ ms sang giây
        
        # Đợi playback hoàn thành
        time.sleep(audio_duration)  # Thêm 0.1s để đảm bảo
        # await asyncio.sleep(audio_duration)
        
        # Đánh dấu playback đã xong
        self.playback_event.clear()

    def listen_for_calls(self):
        """Lắng nghe cuộc gọi từ FreeSWITCH"""
        self.esl_con.events("plain", "CHANNEL_ANSWER CHANNEL_HANGUP")
        print("Đang lắng nghe cuộc gọi...")

        while True:
            e = self.esl_con.recvEvent()
            if e:
                event_name = e.getHeader("Event-Name")

                if event_name == "CHANNEL_ANSWER":
                    uuid = e.getHeader("Unique-ID")
                    sip_to = e.getHeader("variable_sip_to_user")
                    sip_domain = e.getHeader("variable_sip_to_host")
                    media_port = e.getHeader("variable_local_media_port")

                    if sip_to == "media" and sip_domain == "34.29.227.22":
                        print(f"Cuộc gọi mới: UUID {uuid}")
                        
                        # Phát thông điệp chào mừng
                        # self.play_welcome_message(uuid)
                        # self.play_welcome_message(uuid)
                        # Khởi tạo thread xử lý RTP
                        self.active_calls[uuid] = threading.Thread(
                            target=self.handle_rtp_stream,
                            args=(int(media_port), uuid)
                        )
                        self.active_calls[uuid].start()

                elif event_name == "CHANNEL_HANGUP":
                    uuid = e.getHeader("Unique-ID")
                    if uuid in self.active_calls:
                        print(f"Cuộc gọi kết thúc: UUID {uuid}")
                        self.active_calls[uuid].join()
                        del self.active_calls[uuid]

if __name__ == "__main__":
    try:
        bot = FSCallBot()
        bot.listen_for_calls()
    except KeyboardInterrupt:
        print("Đang dừng...")
        bot.is_running = False
    except Exception as e:
        print(f"Lỗi: {e}") 
