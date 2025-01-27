import asyncio
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
import time
from threading import Event

AudioSegment.converter = which("ffmpeg")

class FSCallBotSimple:
    def __init__(self):
        # Khởi tạo các components
        self.speech_processor = SpeechProcessor()
        self.chatbot = ChatbotClient(config)
        self.text_normalizer = TextNormalizer()
        self.playback_event = Event()
        self.active_call = None
        self.is_running = True
        
        # ESL connection
        self.esl_con = ESL.ESLconnection("127.0.0.1", "8021", "ClueCon")
        if not self.esl_con.connected():
            raise Exception("Failed to connect to FreeSWITCH")

    def decode_pcmu_to_pcm16(self, pcmu_data):
        """Giải mã dữ liệu PCMU (G.711u) sang PCM 16-bit."""
        return audioop.alaw2lin(pcmu_data, 2)

    async def play_processing_message(self, uuid):
        """Phát thông báo đang xử lý bất đồng bộ"""
        processing_file = "/home/hm1905/records/processing.wav"
        self.esl_con.execute("playback", processing_file, uuid)
        
        # Tính thời gian của file processing
        audio = AudioSegment.from_wav(processing_file)
        await asyncio.sleep(len(audio) / 1000.0)

    async def process_audio(self, audio_data, uuid):
        """Xử lý audio và tạo phản hồi"""
        try:
            # Bắt đầu phát thông báo đang xử lý song song với xử lý chính
            self.playback_event.set()
            processing_task = asyncio.create_task(self.play_processing_message(uuid))
            
            # Tạo task xử lý chính
            async def main_processing():
                # Chuyển audio thành text
                a = time.time()
                user_text = await self.speech_processor.speech_to_text(audio_data)
                b = time.time()
                print("speech to text: ", b - a)
                
                if not user_text:
                    return None
                    
                print(f"User {uuid}: {user_text}")
                
                # Lấy phản hồi từ chatbot
                a = time.time()
                bot_response = await self.chatbot.get_response(user_text)
                bot_response, _ = self.text_normalizer.check_end_conversation(bot_response)
                normalized_response = self.text_normalizer.normalize_vietnamese_text(bot_response)
                b = time.time()
                print("llm answer: ", b - a)
                print(f"Bot response to {uuid}: {normalized_response}")

                # Chuyển text thành speech và lưu file
                a = time.time()
                response = self.chatbot.client.audio.speech.create(
                    model="tts-1",
                    voice=config.TTS_OPENAI_VOICE,
                    input=normalized_response
                )
                
                output_file = f"/home/hm1905/records/response_{uuid}.wav"
                audio_segment = AudioSegment.from_mp3(io.BytesIO(response.content))
                audio_segment.export(output_file, format='wav')
                b = time.time()
                print("text to speech and save: ", b - a)
                
                return output_file, audio_segment

            # Chạy song song processing_task và main_processing
            main_task = asyncio.create_task(main_processing())
            
            # Đợi một trong hai task hoàn thành trước
            done, pending = await asyncio.wait(
                [processing_task, main_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Nếu processing_task hoàn thành trước, đợi main_task
            if processing_task in done:
                result = await main_task
            else:
                # Nếu main_task hoàn thành trước, hủy processing_task
                processing_task.cancel()
                try:
                    await processing_task
                except asyncio.CancelledError:
                    pass
                result = main_task.result()
                
            if not result:
                return
                
            output_file, audio_segment = result
                
            # Play response qua FreeSWITCH
            a = time.time()
            self.esl_con.execute("uuid_setvar", f"{uuid} playback_terminators none")
            self.esl_con.execute("playback", output_file, uuid)
            
            # Tính thời gian playback dựa trên độ dài audio
            audio_duration = len(audio_segment) / 1000.0
            print("audio_duration: ", audio_duration)
            await asyncio.sleep(audio_duration + 0.2)  # Thêm 0.2s để đảm bảo playback hoàn tất
            
            b = time.time()
            print("playback time: ", b - a)
            
        except Exception as e:
            print(f"Lỗi khi xử lý audio: {e}")
        finally:
            self.playback_event.clear()

    async def handle_rtp_stream(self, port, uuid):
        """Xử lý luồng RTP cho cuộc gọi"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("10.128.0.7", port))
        
        buffer = []
        silence_count = 0
        is_buffering = False
        
        while self.is_running and self.active_call == uuid:
            try:
                if self.playback_event.is_set():
                    await asyncio.sleep(0.1)
                    continue
                
                sock.settimeout(0.1)
                try:
                    data, _ = sock.recvfrom(1024)
                except socket.timeout:
                    continue
                
                if not data:
                    continue
                
                audio_data = data[12:]  # Bỏ RTP header
                
                # Kiểm tra âm lượng
                pcm_data = self.decode_pcmu_to_pcm16(audio_data)
                volume = max(abs(int.from_bytes(pcm_data[i:i+2], 'little', signed=True)) 
                           for i in range(0, len(pcm_data), 2))
                
                if volume > 300:  # Có tiếng nói
                    if not is_buffering:
                        is_buffering = True
                        buffer = []  # Reset buffer khi bắt đầu ghi âm mới
                    silence_count = 0
                    buffer.append(pcm_data)
                else:
                    if is_buffering:  # Chỉ tính silence khi đang trong quá trình buffer
                        silence_count += 1
                        buffer.append(pcm_data)
                
                # Xử lý khi đủ độ im lặng và có dữ liệu trong buffer
                if is_buffering and silence_count > 120 and buffer:  # ~2s im lặng
                    audio_data = b''.join(buffer)
                    await self.process_audio(audio_data, uuid)
                    buffer = []
                    silence_count = 0
                    is_buffering = False  # Reset trạng thái buffering
                    
            except Exception as e:
                print(f"Lỗi trong handle_rtp_stream: {e}")
        
        print(f"Kết thúc xử lý RTP cho UUID {uuid}")
        sock.close()

    async def play_welcome_message(self, uuid):
        """Phát thông điệp chào mừng"""
        welcome_file = "/home/hm1905/records/welcome_trung.wav"
        self.playback_event.set()
        self.esl_con.execute("playback", welcome_file, uuid)
        
        # Tính thời gian của file welcome
        audio = AudioSegment.from_wav(welcome_file)
        await asyncio.sleep(len(audio) / 1000.0)
        self.playback_event.clear()

    async def listen_for_calls(self):
        """Lắng nghe cuộc gọi từ FreeSWITCH"""
        self.esl_con.events("plain", "CHANNEL_ANSWER CHANNEL_HANGUP")
        print("Đang lắng nghe cuộc gọi...")

        async def handle_call(uuid, media_port):
            """Xử lý một cuộc gọi cụ thể"""
            try:
                # Phát thông điệp chào mừng
                await self.play_welcome_message(uuid)
                
                # Xử lý RTP stream
                await self.handle_rtp_stream(int(media_port), uuid)
            except Exception as e:
                print(f"Lỗi khi xử lý cuộc gọi {uuid}: {e}")

        current_call_task = None

        while self.is_running:
            e = self.esl_con.recvEvent()
            if e:
                event_name = e.getHeader("Event-Name")

                if event_name == "CHANNEL_HANGUP":
                    uuid = e.getHeader("Unique-ID")
                    if uuid == self.active_call:
                        print(f"Cuộc gọi kết thúc: UUID {uuid}")
                        self.active_call = None
                        if current_call_task and not current_call_task.done():
                            current_call_task.cancel()
                            try:
                                await current_call_task
                            except asyncio.CancelledError:
                                print(f"Đã hủy xử lý cuộc gọi {uuid}")

                elif event_name == "CHANNEL_ANSWER":
                    uuid = e.getHeader("Unique-ID")
                    sip_to = e.getHeader("variable_sip_to_user")
                    sip_domain = e.getHeader("variable_sip_to_host")
                    media_port = e.getHeader("variable_local_media_port")

                    if sip_to == "media" and sip_domain == "34.29.227.22":
                        print(f"Cuộc gọi mới: UUID {uuid}")
                        
                        # Hủy cuộc gọi cũ nếu có
                        if current_call_task and not current_call_task.done():
                            current_call_task.cancel()
                            try:
                                await current_call_task
                            except asyncio.CancelledError:
                                print("Đã hủy cuộc gọi cũ")
                        
                        self.active_call = uuid
                        # Tạo task mới cho cuộc gọi
                        current_call_task = asyncio.create_task(
                            handle_call(uuid, media_port)
                        )

            # Cho phép các event khác được xử lý
            await asyncio.sleep(0.1)

if __name__ == "__main__":
    try:
        bot = FSCallBotSimple()
        asyncio.run(bot.listen_for_calls())
    except KeyboardInterrupt:
        print("Đang dừng...")
        bot.is_running = False
    except Exception as e:
        print(f"Lỗi: {e}")
    finally:
        bot.is_running = False 
