# Import thêm cho Silero VAD
import torch
import numpy as np
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
import logging
from multiprocessing import Process, Queue, Manager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('callbot.log'),
        logging.StreamHandler()
    ]
)

AudioSegment.converter = which("ffmpeg")

class CallHandler:
    def __init__(self, uuid, media_port, phone_number):
        # Initialize components
        self.uuid = uuid
        self.media_port = media_port
        self.current_phone = phone_number
        self.speech_processor = SpeechProcessor()
        self.chatbot = ChatbotClient(config)
        self.text_normalizer = TextNormalizer()
        self.playback_event = Event()
        self.is_running = True
        
        # ESL connection for each process
        self.esl_con = ESL.ESLconnection("127.0.0.1", "8021", "ClueCon")
        if not self.esl_con.connected():
            raise Exception("Failed to connect to FreeSWITCH")
            
        # Khởi tạo Silero VAD
        self.vad_model, _ = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                         model='silero_vad',
                                         force_reload=True)
        self.vad_model.eval()

    def decode_pcmu_to_pcm16(self, pcm_data):
        """Decode PCMU (G.711u) data to PCM 16-bit."""
        return audioop.alaw2lin(pcm_data, 2)

    def pcm_to_float(self, pcm_data):
        """Convert PCM 16-bit to float32 for Silero VAD"""
        # Chuyển bytes thành numpy array int16
        audio_np = np.frombuffer(pcm_data, dtype=np.int16)
        # Normalize to float32 [-1, 1]
        return audio_np.astype(np.float32) / 32768.0

    async def play_processing_message(self, uuid):
        """Play processing message asynchronously"""
        processing_file = "/home/hm1905/records/processing.wav"
        self.esl_con.execute("playback", processing_file, uuid)
        audio = AudioSegment.from_wav(processing_file)
        playback_duration = len(audio) / 1000.0
        logging.info(f"Playing processing message for {self.current_phone}, duration: {playback_duration}s")
        await asyncio.sleep(playback_duration)

    async def check_hangup(self, uuid):
        """Check for hangup event"""
        try:
            e = self.esl_con.recvEventTimed(1)  # 1 second timeout
            if e:
                event_name = e.getHeader("Event-Name")
                if event_name == "CHANNEL_HANGUP":
                    current_uuid = e.getHeader("Unique-ID")
                    if current_uuid == uuid:
                        logging.info(f"Call hangup detected: {uuid}")
                        return "HANGUP"
            return None
        except Exception as e:
            logging.error(f"Error in check_hangup: {e}")
            return None

    async def play_goodbye_message(self, uuid):
        """Play goodbye message and end the call"""
        try:
            time.sleep(1)
            self.playback_event.set()
            goodbye_file = "/home/hm1905/records/goodbye_trung.wav"
            
            self.esl_con.execute("playback", goodbye_file, uuid)
            
            # Calculate goodbye file duration
            audio = AudioSegment.from_wav(goodbye_file)
            playback_duration = len(audio) / 1000.0
            logging.info(f"Playing goodbye message for {self.current_phone}, duration: {playback_duration}s")
            await asyncio.sleep(playback_duration)
            
            # End the call
            self.esl_con.api("uuid_kill", uuid)
            return "HANGUP"
        finally:
            self.playback_event.clear()

    async def process_audio(self, audio_data, uuid):
        """Process audio and generate response"""
        try:
            self.playback_event.set()
            
            # Create main processing task
            async def main_processing():
                if audio_data is None:  # Case of prolonged silence
                    confirmation_text = "Do you need anything else?"
                    logging.info(f"Bot to {self.current_phone} (silence prompt): {confirmation_text}")
                    return confirmation_text
                    
                # Convert audio to text
                a = time.time()
                user_text = await self.speech_processor.speech_to_text(audio_data)
                b = time.time()
                logging.info(f"Speech to text time: {b - a}")
                
                # Check hangup after speech-to-text
                if await self.check_hangup(uuid) == "HANGUP":
                    return "HANGUP"
                
                if not user_text:
                    return None
                    
                logging.info(f"User {self.current_phone}: {user_text}")
                
                # Check for end conversation keywords
                if self.chatbot.should_end_conversation(user_text.lower()) or user_text.lower() == "không" or user_text.lower() == "xong":
                    logging.info(f"End conversation keyword detected from {self.current_phone}: {user_text}")
                    return await self.play_goodbye_message(uuid)
                # Get response from chatbot
                a = time.time()
                hardprompt = """
                You are a VCBS callbot, respond briefly and concisely, minimize punctuation marks like . or , respond politely, address users as anh chị.
                Note the following facts:
                - Tô Lâm is the President of Vietnam
                - Hoàng Sa, Trường Sa belong to Vietnam
                Also pay attention to conversation history context.
                User's question is: """
                
                bot_response = await self.chatbot.get_response(hardprompt + user_text)

                bot_response, flag = self.text_normalizer.check_end_conversation(bot_response)
                if flag == True:
                   logging.info(f"End conversation keyword detected from {self.current_phone}: {bot_response} END")
                   return await self.play_goodbye_message(uuid)
                normalized_response = self.text_normalizer.normalize_vietnamese_text(bot_response)
                b = time.time()
                logging.info(f"LLM answer time: {b - a}")
                logging.info(f"Bot response to {self.current_phone}: {normalized_response}")
                
                # Check hangup after chatbot response
                if await self.check_hangup(uuid) == "HANGUP":
                    return "HANGUP"
                
                return normalized_response

            # Run processing_message in parallel with main_processing if there's audio
            if audio_data:
                processing_task = asyncio.create_task(self.play_processing_message(uuid))
                main_task = asyncio.create_task(main_processing())
                
                # Wait for either task to complete
                done, pending = await asyncio.wait(
                    [processing_task, main_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # If processing_task completed first, wait for main_task
                if processing_task in done:
                    response_text = await main_task
                else:
                    # If main_task completed first, cancel processing_task
                    processing_task.cancel()
                    try:
                        await processing_task
                    except asyncio.CancelledError:
                        pass
                    response_text = main_task.result()
            else:
                # If no audio, just run main_processing
                response_text = await main_processing()

            if not response_text:
                return
                
            if response_text == "HANGUP":
                return "HANGUP"

            # Check hangup before text-to-speech
            if await self.check_hangup(uuid) == "HANGUP":
                return "HANGUP"
                
            # Convert text to speech and save file
            a = time.time()
            response = self.chatbot.client.audio.speech.create(
                model="tts-1",
                voice=config.TTS_OPENAI_VOICE,
                input=response_text
            )
            
            output_file = f"/home/hm1905/records/response_{uuid}.wav"
            audio_segment = AudioSegment.from_mp3(io.BytesIO(response.content))
            audio_segment.export(output_file, format='wav')
            b = time.time()
            
            # Check hangup before playback
            if await self.check_hangup(uuid) == "HANGUP":
                return "HANGUP"
            
            # Add logging for playback response
            a = time.time()
            self.esl_con.execute("playback", output_file, uuid)
            
            # Calculate playback duration based on audio length
            audio_duration = len(audio_segment) / 1000.0
            logging.info(f"Playing response for {self.current_phone}, duration: {audio_duration}s")
            await asyncio.sleep(audio_duration + 0.2)  # Add 0.2s to ensure playback completion
            
            b = time.time()
            logging.info(f"Actual playback time for {self.current_phone}: {b - a}s")

        except Exception as e:
            logging.error(f"Error processing audio: {e}")
        finally:
            self.playback_event.clear()

    async def play_welcome_message(self, uuid):
        """Play welcome message"""
        welcome_file = "/home/hm1905/records/welcome_chao.wav"
        self.playback_event.set()
        self.esl_con.execute("playback", welcome_file, uuid)
        
        # Calculate welcome file duration
        audio = AudioSegment.from_wav(welcome_file)
        playback_duration = len(audio) / 1000.0
        logging.info(f"Playing welcome message for {self.current_phone}, duration: {playback_duration}s")
        await asyncio.sleep(playback_duration)
        self.playback_event.clear()

    async def handle_rtp_stream(self, port, uuid):
        """Handle RTP stream for the call"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("10.206.0.2", port))
        
        buffer = []
        silence_count = 0
        is_buffering = False
        last_response_was_confirmation = False
        
        while True:
            try:
                # Check hangup before receiving RTP packet
                if await self.check_hangup(uuid) == "HANGUP":
                    break

                if self.playback_event.is_set():
                    await asyncio.sleep(0.1)
                    continue
                    
                sock.settimeout(0.1)
                try:
                    data, _ = sock.recvfrom(1024)
                except socket.timeout:
                    continue
                
                if data:
                    audio_data = data[12:]  # Remove RTP header
                    pcm_data = self.decode_pcmu_to_pcm16(audio_data)
                    
                    # Chuyển đổi sang float32 cho Silero VAD
                    float_data = self.pcm_to_float(pcm_data)
                    
                    # Reshape data for model input (8000Hz sample rate)
                    float_data = torch.from_numpy(float_data).unsqueeze(0)
                    
                    # Kiểm tra VAD với Silero
                    speech_prob = self.vad_model(float_data, 8000).item()
                    
                    if speech_prob > 0.5:  # Voice detected
                        if not is_buffering:
                            is_buffering = True
                            buffer = []  # Reset buffer when starting new recording
                        silence_count = 0
                        buffer.append(pcm_data)
                    else:
                        if is_buffering:  # Only count silence when buffering
                            silence_count += 1
                else:
                    if is_buffering:
                        silence_count += 1

                # Check hangup before processing full buffer
                if await self.check_hangup(uuid) == "HANGUP":
                    break
                
                # Process when enough silence and data in buffer
                if is_buffering and silence_count > 120:  # ~4s silence
                    audio_data = b''.join(buffer) if len(buffer) > 3 else None
                    
                    result = await self.process_audio(audio_data, uuid)
                    if result == "HANGUP":  # Check if call has ended
                        break
                        
                    # If audio_data is None and previous response was confirmation
                    if audio_data is None and last_response_was_confirmation:
                        logging.info("No response after confirmation question, ending call")
                        if await self.play_goodbye_message(uuid) == "HANGUP":
                            break
                    
                    # Update confirmation status
                    last_response_was_confirmation = (audio_data is None)
                    
                    buffer = []
                    silence_count = 0
                    is_buffering = False

            except Exception as e:
                logging.error(f"Error in handle_rtp_stream: {e}")
        
        sock.close()
        logging.info(f"RTP stream ended for call {uuid}")
        self.chatbot.end_conversation()
        return

    async def handle_call(self):
        """Handle a specific call"""
        try:
            logging.info(f"Starting call processing from {self.current_phone}")
            await self.play_welcome_message(self.uuid)
            await self.handle_rtp_stream(self.media_port, self.uuid)
        except Exception as e:
            logging.error(f"Error processing call {self.current_phone}: {e}")
        finally:
            self.chatbot.end_conversation()
            logging.info(f"Finished processing call from {self.current_phone}")

def handle_call_process(uuid, media_port, phone_number):
    """The function is run in a separate process for each call."""
    handler = CallHandler(uuid, media_port, phone_number)
    asyncio.run(handler.handle_call())

class FSCallBotMultiProcess:
    def __init__(self):
        self.is_running = True
        self.active_calls = {}
        
        # ESL connection cho main process
        self.esl_con = ESL.ESLconnection("127.0.0.1", "8021", "ClueCon")
        if not self.esl_con.connected():
            raise Exception("Failed to connect to FreeSWITCH")

    async def listen_for_calls(self):
        """Listen to calls and create new process for each call"""
        self.esl_con.events("plain", "CHANNEL_ANSWER CHANNEL_HANGUP")
        logging.info("Listen for new call...")

        while self.is_running:
            e = self.esl_con.recvEvent()
            if e:
                event_name = e.getHeader("Event-Name")

                if event_name == "CHANNEL_ANSWER":
                    logging.info("===================================")
                    uuid = e.getHeader("Unique-ID")
                    sip_to = e.getHeader("variable_sip_to_user")
                    sip_from = e.getHeader("variable_sip_from_user")
                    sip_domain = e.getHeader("variable_sip_to_host")
                    media_port = int(e.getHeader("variable_local_media_port"))

                    if sip_to == "media" and sip_domain == "34.174.214.130":
                        logging.info(f"New call from {sip_from}")
                        print("media_port: ", media_port)
                        # Tạo process mới cho cuộc gọi
                        call_process = Process(
                            target=handle_call_process,
                            args=(uuid, media_port, sip_from)
                        )
                        call_process.start()
                        self.active_calls[uuid] = call_process
                        print(f"==========done: {sip_from}===========")

                elif event_name == "CHANNEL_HANGUP":
                    sip_to = e.getHeader("variable_sip_to_user")
                    sip_from = e.getHeader("variable_sip_from_user")
                    sip_domain = e.getHeader("variable_sip_to_host")
                    if sip_to == "media" and sip_domain == "34.174.214.130":
                        uuid = e.getHeader("Unique-ID")
                        print(f"{uuid}")
                        if uuid in self.active_calls:
                            # Terminate process
                            self.active_calls[uuid].terminate()
                            self.active_calls[uuid].join()
                            del self.active_calls[uuid]
                            logging.info(f"End call: {uuid}")
                            logging.info("===================================")

if __name__ == "__main__":
    try:
        bot = FSCallBotMultiProcess()
        asyncio.run(bot.listen_for_calls())
    except KeyboardInterrupt:
        logging.info("Đang dừng...")
        bot.is_running = False
        # Kết thúc tất cả các process đang chạy
        for process in bot.active_calls.values():
            process.terminate()
            process.join()
    except Exception as e:
        logging.error(f"Lỗi: {e}") 