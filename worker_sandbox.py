import pika
import json
import time
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
import time
from threading import Event
import logging
from datetime import datetime
import os
import webrtcvad
import numpy as np
import noisereduce as nr
# import aiofiles

from dotenv import load_dotenv

load_dotenv()

# Thiết lập logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
log_level_dict = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

logging.basicConfig(
    level=log_level_dict.get(LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.getenv('LOGGING_FILE', 'callbot.log')),
        logging.StreamHandler()
    ]
)


# Cấu hình audio cho WebRTC VAD
SAMPLE_RATE = int(os.getenv('AUDIO_RATE', '8000'))
FRAME_DURATION_MS = int(os.getenv('FRAME_DURATION_MS', '20'))
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000) * 2  # 2 bytes/sample

# Cấu hình VAD
VAD_MODE = int(os.getenv('VAD_MODE', '3'))  # 0: ít nhạy, 3: nhạy nhất
vad = webrtcvad.Vad(VAD_MODE)

# Cấu hình phát hiện tiếng nói
CONSECUTIVE_SPEECH_FRAMES_REQUIRED = int(os.getenv('CONSECUTIVE_FRAMES', '3'))  # Số frame liên tiếp cần để xác nhận tiếng nói
MIN_VOLUME_THRESHOLD = int(os.getenv('MIN_VOLUME', '500'))    # Ngưỡng âm lượng tối thiểu để xem xét
SPEECH_VOLUME_THRESHOLD = int(os.getenv('SPEECH_VOLUME', '800'))  # Ngưỡng âm lượng để xác nhận tiếng nói
SILENCE_FRAMES_THRESHOLD = int(os.getenv('SILENCE_FRAMES', '60'))  # Số frame im lặng để kết thúc ghi âm
LONG_SILENCE_THRESHOLD = int(os.getenv('LONG_SILENCE_THRESHOLD', '250'))
MIN_BUFFER_SIZE = int(os.getenv('MIN_BUFFER_SIZE', '15'))  # Số frame tối thiểu trong buffer

# Cấu hình bật/tắt khử nhiễu để tiết kiệm CPU
ENABLE_NOISE_REDUCTION = os.getenv('ENABLE_NOISE_REDUCTION', 'true').lower() == 'true'
logging.info(f"Starting with VAD mode: {VAD_MODE}, Sample rate: {SAMPLE_RATE}, Min volume: {MIN_VOLUME_THRESHOLD}, Speech volume: {SPEECH_VOLUME_THRESHOLD}")

# Biến global để theo dõi frame liên tiếp
consecutive_speech_frames = 0  # Biến đếm số frame liên tiếp phát hiện tiếng nói

def frame_generator(frame_duration_ms, audio, sample_rate):
    """Chia dữ liệu audio thành các frame có độ dài cố định."""
    n = int(sample_rate * frame_duration_ms / 1000) * 2  # bytes per frame
    offset = 0
    while offset + n <= len(audio):
        yield audio[offset:offset+n]
        offset += n

def apply_noise_suppression(pcm_data, sample_rate=SAMPLE_RATE):
    """Áp dụng noise suppression với thư viện noisereduce.
    
    Sử dụng cấu hình mạnh hơn để loại bỏ tiếng ồn nền triệt để.
    """
    # Nếu không bật tính năng khử nhiễu, trả về dữ liệu gốc
    if not ENABLE_NOISE_REDUCTION:
        return pcm_data
        
    try:
        # Kiểm tra nếu dữ liệu quá ngắn, trả về dữ liệu gốc
        if len(pcm_data) < 1000:
            return pcm_data
            
        # Chuyển đổi bytes sang numpy array dạng int16
        audio_np = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
        
        # Đảm bảo audio_np không trống
        if len(audio_np) == 0:
            return pcm_data
        
        # Cải thiện: sử dụng cấu hình đơn giản hơn để tránh lỗi
        try:
            reduced_noise = nr.reduce_noise(
                y=audio_np, 
                sr=sample_rate,
                prop_decrease=os.getenv('PROP_DECREASE', '0.75')  # Giảm xuống để tránh lỗi
            )
            return reduced_noise.astype(np.int16).tobytes()
        except Exception as inner_e:
            logging.error(f"Error in noise reduction algorithm: {inner_e}")
            return pcm_data  # Trả về dữ liệu gốc nếu lỗi
            
    except Exception as e:
        logging.error(f"Error in noise suppression: {e}")
        return pcm_data  # Return original data if error occurs

AudioSegment.converter = which("ffmpeg")

# ESL connection
esl_con = ESL.ESLconnection(os.getenv('ESL_HOST'), os.getenv('ESL_PORT'), os.getenv('ESL_PASSWORD'))
if not esl_con.connected():
    raise Exception("Failed to connect to FreeSWITCH")

speech_processor = SpeechProcessor()
chatbot = ChatbotClient()
text_normalizer = TextNormalizer()
playback_event = Event()
active_call = None
is_running = True
current_phone = None
start_time = None

import psycopg2
from psycopg2 import sql


#Postgres insert. Need Serious rework
def data_insert(uuid, number, step, output, processing_time):
    conn = psycopg2.connect(
      dbname=os.getenv('POSTGRES_DB'), 
      user=os.getenv('POSTGRES_USER'), 
      password=os.getenv('POSTGRES_PASSWORD'), 
      host=os.getenv('POSTGRES_HOST'),
      port=int(os.getenv('POSTGRES_PORT')) 
    )
    now = datetime.now()    
    cursor = conn.cursor()
    insert_query = """
      INSERT INTO callbot.activity_history (uuid, number, step, output, processing_time, time)
      VALUES (%s, %s, %s, %s, %s, %s)
    """
    payload = (uuid, number, step, output, processing_time, now)
    cursor.execute(insert_query, payload)
    conn.commit()
    cursor.close()
    conn.close()


def decode_pcmu_to_pcm16(pcmu_data):
    """Giải mã dữ liệu PCMU (G.711u) sang PCM 16-bit.
    
    Chuẩn bị dữ liệu audio cho xử lý WebRTC VAD, đảm bảo định dạng và tỉ lệ mẫu phù hợp.
    """
    try:
        # Kiểm tra dữ liệu đầu vào
        if not pcmu_data or len(pcmu_data) < 2:
            return b''
            
        # Giải mã dữ liệu PCMU sang PCM 16-bit
        pcm_data = audioop.alaw2lin(pcmu_data, 2)
        
        try:
            # WebRTC VAD yêu cầu dữ liệu ở định dạng PCM 16-bit, 16kHz
            # Chuyển đổi tỉ lệ mẫu từ 8kHz (điển hình cho SIP/RTP) sang 16kHz (cần cho WebRTC VAD)
            
            # Khắc phục: kiểm tra giá trị SAMPLE_RATE trước khi chuyển đổi
            # Chỉ chuyển đổi nếu khác biệt hẳn với 8000Hz
            if abs(SAMPLE_RATE - 8000) > 100:  # Đảm bảo khác biệt ít nhất 100Hz
                pcm_data = audioop.ratecv(pcm_data, 2, 1, 8000, SAMPLE_RATE, None)[0]
        except Exception as rate_error:
            # Nếu lỗi chuyển đổi tỉ lệ mẫu, ghi log và tiếp tục với dữ liệu gốc
            logging.error(f"Sample rate conversion error: {rate_error}")
        
        return pcm_data
    except Exception as e:
        logging.error(f"Error decoding PCMU to PCM16: {e}")
        return b''  # Return empty bytes on error

async def play_processing_message(uuid, current_phone):
    """Phát thông báo đang xử lý bất đồng bộ"""
    processing_file = os.getenv('CONTAINER_PROCESSING_FILE') 
    esl_con.execute("playback", processing_file.replace(os.getenv('CONTAINER_PROCESSING_FILE'), os.getenv('PROCESSING_FILE')), uuid)
    
    # Tính thời gian của file processing
    audio = AudioSegment.from_wav(processing_file)
    playback_duration = len(audio) / 1000.0
    logging.info(f"Playing processing message for {current_phone}, duration: {playback_duration}s")
    await asyncio.sleep(playback_duration)

async def check_hangup(uuid, current_phone):
    """Kiểm tra sự kiện hangup"""
    try:
        # print("here Hangup")
        e = esl_con.recvEventTimed(1)  # Timeout 1 giây
        if e:
            a = time.time()
            event_name = e.getHeader("Event-Name")
            if event_name == "CHANNEL_HANGUP":
                current_uuid = e.getHeader("Unique-ID")
                if current_uuid == uuid:
                    print(f"Phát hiện cuộc gọi kết thúc: {uuid}")
                    b = time.time()
                    data_insert(uuid, current_phone, "HANGUP","None",b - a)
                    return "HANGUP"
        return None
    except Exception as e:
        print(f"Lỗi trong check_hangup: {e}")
        return None

async def play_goodbye_message(uuid, current_phone):
    """Phát thông điệp tạm biệt và kết thúc cuộc gọi"""
    try:
        time.sleep(1)
        playback_event.set()
        goodbye_file = os.getenv('CONTAINER_GOODBYE_FILE')
        
        esl_con.execute("playback", goodbye_file.replace(os.getenv('CONTAINER_GOODBYE_FILE'), os.getenv('GOODBYE_FILE')), uuid)
        
        # Tính thời gian của file goodbye
        audio = AudioSegment.from_wav(goodbye_file)
        playback_duration = len(audio) / 1000.0
        logging.info(f"Playing goodbye message for {current_phone}, duration: {playback_duration}s")
        await asyncio.sleep(playback_duration)
        
        # Kết thúc cuộc gọi
        esl_con.api("uuid_kill", uuid)
        data_insert(uuid, current_phone, "GOODBYE", "GOODBYE", playback_duration)
        return "HANGUP"
    finally:
        playback_event.clear()

async def process_audio(audio_data, uuid, current_phone):
    """Xử lý audio và tạo phản hồi"""
    try:
        playback_event.set()
        
        # Tạo task xử lý chính
        async def main_processing():
            if audio_data is None:  # Trường hợp im lặng quá lâu
                confirmation_text = "anh chị có cần gì nữa không ạ"
                # print(f"Bot to {uuid} (silence prompt): {confirmation_text}")
                logging.info(f"Bot to {current_phone} (silence prompt): {confirmation_text}")
                return confirmation_text
                
            
            a = time.time()
            
            user_text = await speech_processor.speech_to_text(audio_data)
            b = time.time()
            # print("speech to text: ", b - a)
            logging.info(f"Speech to text time: {b - a}")
            procssing_time_asr = b - a
            data_insert(uuid, current_phone, "ASR", user_text, procssing_time_asr)
            
            # Kiểm tra hangup sau speech-to-text
            if await check_hangup(uuid, current_phone) == "HANGUP":
                return "HANGUP"
            
            if not user_text:
                return None
                
            # print(f"User {uuid}: {user_text}")
            logging.info(f"User {current_phone}: {user_text}")
            
            # Kiểm tra từ khóa kết thúc
            if chatbot.should_end_conversation(user_text.lower()) or user_text.lower() == "không" or user_text.lower() == "xong":
                # print(f"Phát hiện từ khóa kết thúc: {user_text}")
                logging.info(f"Phát hiện từ khóa kết thúc từ {current_phone}: {user_text}")
                return await play_goodbye_message(uuid, current_phone)

            # Lấy phản hồi từ chatbot
            a = time.time()
            hardprompt = os.getenv('HARD_PROMPT')
            
            bot_response = await chatbot.get_response(hardprompt + user_text)

            bot_response, flag = text_normalizer.check_end_conversation(bot_response)
            if flag == True:
                logging.info(f"Phát hiện từ khóa kết thúc từ {current_phone}: {bot_repsonse} END")
                return await play_goodbye_message(uuid, current_phone)
            normalized_response = text_normalizer.normalize_vietnamese_text(bot_response)
            b = time.time()
            # print("llm answer: ", b - a)
            logging.info(f"LLM answer time: {b - a}")
            processing_time_llm = b-a
            data_insert(uuid, current_phone, "LLM", normalized_response, processing_time_llm)
            # print(f"Bot response to {uuid}: {normalized_response}")
            logging.info(f"Bot response to {current_phone}: {normalized_response}")
            
            # Kiểm tra hangup sau khi có response từ chatbot
            if await check_hangup(uuid,current_phone) == "HANGUP":
                return "HANGUP"
            
            return normalized_response

        # Chạy processing_message song song với main_processing nếu có audio
        if audio_data:
            processing_task = asyncio.create_task(play_processing_message(uuid, current_phone))
            main_task = asyncio.create_task(main_processing())
            
            # Đợi một trong hai task hoàn thành
            done, pending = await asyncio.wait(
                [processing_task, main_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Nếu processing_task hoàn thành trước, đợi main_task
            if processing_task in done:
                response_text = await main_task
            else:
                # Nếu main_task hoàn thành trước, hủy processing_task
                processing_task.cancel()
                try:
                    await processing_task
                except asyncio.CancelledError:
                    pass
                response_text = main_task.result()
        else:
            # Nếu không có audio, chỉ chạy main_processing
            response_text = await main_processing()

        if not response_text:
            return
            
        if response_text == "HANGUP":
            return "HANGUP"

        # Kiểm tra hangup trước khi text-to-speech
        if await check_hangup(uuid, current_phone) == "HANGUP":
            return "HANGUP"
            
        # Chuyển text thành speech và lưu file
        a = time.time()
        response = chatbot.client.audio.speech.create(
            model=os.getenv("TTS_MODEL"),
            voice=os.getenv("TTS_OPENAI_VOICE"),
            input=response_text
        )
        
        output_file = os.getenv('CONTAINER_RECORD_PATH') + f"/response_{uuid}.wav"
        audio_segment = AudioSegment.from_mp3(io.BytesIO(response.content))
        audio_segment.export(output_file, format='wav')
        b = time.time()
        print("text to speech and save: ", b - a)
        processing_time_tts = b-a
        data_insert(uuid, current_phone, "TTS", "", processing_time_tts)
        
        
        # Kiểm tra hangup trước khi playback
        if await check_hangup(uuid, current_phone) == "HANGUP":
            return "HANGUP"
        
        # Thêm logging cho playback response
        a = time.time()
        esl_con.execute("uuid_setvar", f"{uuid} playback_terminators none")
        esl_con.execute("playback", output_file.replace(os.getenv('CONTAINER_RECORD_PATH'), os.getenv('RECORD_PATH')), uuid)
        
        # Tính thời gian playback dựa trên độ dài audio
        audio_duration = len(audio_segment) / 1000.0
        logging.info(f"Playing response for {current_phone}, duration: {audio_duration}s")
        # print("audio_duration: ", audio_duration)
        await asyncio.sleep(audio_duration + 0.2)  # Thêm 0.2s để đảm bảo playback hoàn tất
        
        b = time.time()
        
        # print("playback time: ", b - a)
        logging.info(f"Actual playback time for {current_phone}: {b - a}s")
        processing_time_tts_playback = b-a
        data_insert(uuid, current_phone, "PLAYBACK", "", processing_time_tts_playback)
        
    except Exception as e:
        print(f"Lỗi khi xử lý audio: {e}")
        return "HANGUP"
    finally:
        playback_event.clear()

async def handle_rtp_stream(port, uuid, current_phone, ch, method):
    """Xử lý luồng RTP cho cuộc gọi"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((os.getenv('RTP_HOST'), int(port))) 
    
    logging.info(f"RTP Stream started for {current_phone} on port {port} with VAD mode {VAD_MODE}")
    
    buffer = []
    silence_count = 0
    is_buffering = False
    last_response_was_confirmation = 0
    
    global start_time, consecutive_speech_frames
    start_time = time.time()
    consecutive_speech_frames = 0
    
    # Biến thống kê cho debug
    packet_count = 0
    speech_frames_detected = 0
    processing_attempts = 0
    total_silence_count = 0
    
    while True:
        try:
            # Kiểm tra hangup trước khi nhận RTP packet
            if await check_hangup(uuid, current_phone) == "HANGUP":
                logging.info(f"Hangup detected for {current_phone}, ending RTP stream")
                break

            if playback_event.is_set():
                await asyncio.sleep(0.1)
                continue
                
            sock.settimeout(0.1)
            try:
                data, _ = sock.recvfrom(1024)
                packet_count += 1
                if packet_count % 500 == 0:  # Log mỗi 500 gói
                    logging.debug(f"Processed {packet_count} RTP packets, detected {speech_frames_detected} speech frames")
            except socket.timeout:
                continue
            
            if data:
                # Loại bỏ RTP header (12 bytes)
                audio_data = data[12:]
                
                # Giải mã từ PCMU sang PCM16
                pcm_data = decode_pcmu_to_pcm16(audio_data)
                
                # Áp dụng noise suppression để làm sạch tín hiệu
                # pcm_data_clean = apply_noise_suppression(pcm_data)
                pcm_data_clean = pcm_data
                # Phân chia dữ liệu thành các frame 20ms
                frames = list(frame_generator(FRAME_DURATION_MS, pcm_data_clean, SAMPLE_RATE))
                
                # Kiểm tra xem có frame nào chứa giọng nói hay không
                current_frame_has_speech = False
                speech_detected = False  # Mặc định không phát hiện tiếng nói
                
                
                if frames:
                    try:
                        # Tính toán giá trị âm lượng TỐI ĐA (không phải trung bình)
                        max_volume = 0
                        print('len pcm_data: ',len(pcm_data))
                        # Đảm bảo pcm_data có đủ chiều dài
                        if len(pcm_data) >= 2:
                            for i in range(0, len(pcm_data) - 1, 2):
                                volume = abs(int.from_bytes(pcm_data[i:i+2], 'little', signed=True))
                                if volume > max_volume:
                                    max_volume = volume
                                    
                        print('max_volume: ', max_volume)
                        
                        # Đơn giản hóa: Chỉ kiểm tra âm lượng trước, nếu âm lượng đủ lớn thì mới xử lý VAD
                        # Ngưỡng âm lượng tối thiểu để xử lý VAD
                        if max_volume > MIN_VOLUME_THRESHOLD:
                            # Kiểm tra từng frame
                            valid_frames = [frame for frame in frames if len(frame) == FRAME_SIZE]
                            print('len valid_frames: ',len(valid_frames))
                            # Nếu có ít nhất một frame hợp lệ
                            if valid_frames:
                                # Kiểm tra tất cả các frame hợp lệ thay vì giới hạn 5 frame
                                speech_frames = 0
                                
                                for frame in valid_frames:
                                    try:
                                        if vad.is_speech(frame, SAMPLE_RATE):
                                            speech_frames += 1
                                    except Exception as frame_error:
                                        logging.debug(f"Error checking frame: {frame_error}")
                                        continue
                                
                                print('speech_frames: ',speech_frames)
                                # Phát hiện tiếng nói nếu có ít nhất 1 frame có tiếng nói và âm lượng đủ lớn
                                current_frame_has_speech = (speech_frames > 0) and (max_volume > SPEECH_VOLUME_THRESHOLD)
                                print('current_frame_has_speech: ',current_frame_has_speech)
                            else:
                                # Sử dụng phát hiện dựa trên âm lượng nếu không có frame hợp lệ
                                current_frame_has_speech = max_volume > SPEECH_VOLUME_THRESHOLD
                        else:
                            current_frame_has_speech = False
                        
                        # Cập nhật biến đếm frame liên tiếp
                        if current_frame_has_speech:
                            consecutive_speech_frames += 1
                            # Log khi phát hiện tiếng nói
                            if consecutive_speech_frames >= CONSECUTIVE_SPEECH_FRAMES_REQUIRED:
                                print(f"Phát hiện tiếng nói! Frame liên tiếp: {consecutive_speech_frames}/{CONSECUTIVE_SPEECH_FRAMES_REQUIRED}, Max Volume: {max_volume}")
                        else:
                            # Giảm dần số đếm thay vì reset về 0
                            consecutive_speech_frames = max(0, consecutive_speech_frames - 1)
                            
                        # Chỉ coi là phát hiện tiếng nói khi đủ số frame liên tiếp
                        speech_detected = consecutive_speech_frames >= CONSECUTIVE_SPEECH_FRAMES_REQUIRED
                        
                        print('consecutive_speech_frames: ',consecutive_speech_frames)
                        print('speech_detected: ', speech_detected)
                    except Exception as e:
                        logging.error(f"VAD error: {e}")
                        # Fallback to simpler volume-based detection if VAD fails
                        try:
                            # Tính toán âm lượng tối đa một cách an toàn
                            max_volume = 0
                            if len(pcm_data) >= 2:
                                for i in range(0, len(pcm_data) - 1, 2):
                                    vol = abs(int.from_bytes(pcm_data[i:i+2], 'little', signed=True))
                                    if vol > max_volume:
                                        max_volume = vol
                            
                            print('fallback max_volume: ', max_volume)
                            current_frame_has_speech = max_volume > SPEECH_VOLUME_THRESHOLD  # Sử dụng ngưỡng cấu hình
                            
                            # Cập nhật biến đếm frame liên tiếp trong trường hợp fallback
                            if current_frame_has_speech:
                                consecutive_speech_frames += 1
                                # Log khi phát hiện tiếng nói
                                if consecutive_speech_frames >= CONSECUTIVE_SPEECH_FRAMES_REQUIRED:
                                    print(f"Fallback: Phát hiện tiếng nói! Frame liên tiếp: {consecutive_speech_frames}/{CONSECUTIVE_SPEECH_FRAMES_REQUIRED}, Max Volume: {max_volume}")
                            else:
                                # Giảm dần số đếm thay vì reset về 0
                                consecutive_speech_frames = max(0, consecutive_speech_frames - 1)
                            
                            # Chỉ coi là phát hiện tiếng nói khi đủ số frame liên tiếp
                            speech_detected = consecutive_speech_frames >= CONSECUTIVE_SPEECH_FRAMES_REQUIRED
                            
                            print('consecutive_speech_frames: ',consecutive_speech_frames)
                            print('speech_detected: ',speech_detected)
                        except Exception as inner_e:
                            logging.error(f"Fallback detection error: {inner_e}")
                            speech_detected = False  # Nếu tất cả đều thất bại, không phát hiện tiếng nói
                
                # Nếu không phát hiện speech trong frame hiện tại và không đủ frame liên tiếp, giảm dần biến đếm
                if not current_frame_has_speech:
                    # Giảm dần số đếm thay vì reset về 0
                    # silence_count += 1
                    consecutive_speech_frames = max(0, consecutive_speech_frames - 1)
                
                if speech_detected:
                    speech_frames_detected += 1
                    if not is_buffering:
                        is_buffering = True
                        buffer = []  # Reset buffer khi bắt đầu ghi âm mới
                        logging.info(f"{current_phone} on port {port}: Speech detected, buffering started")
                    silence_count = 0
                    buffer.append(pcm_data_clean)
                    print(pcm_data_clean)
                else:
                    if is_buffering:
                        silence_count += 1
                        if silence_count % 10 == 0:  # Log mỗi 20 frame im lặng
                            logging.debug(f"Silence count: {silence_count}/{SILENCE_FRAMES_THRESHOLD}, buffer size: {len(buffer)}")
                    total_silence_count += 1
            else:
                if is_buffering:
                    silence_count += 1
                total_silence_count += 1
                
            # Kiểm tra hangup trước khi xử lý buffer đầy
            if await check_hangup(uuid, current_phone) == "HANGUP":
                break
                
                
            if is_buffering and silence_count > SILENCE_FRAMES_THRESHOLD:  # Sử dụng thông số cấu hình
                processing_attempts += 1
                logging.info(f"{current_phone}: Speech segment completed, processing audio (attempt #{processing_attempts})")
                
                # Đảm bảo buffer không rỗng và có đủ dữ liệu
                if buffer and len(buffer) > MIN_BUFFER_SIZE:  # Sử dụng thông số cấu hình
                    try:
                        audio_data = b''.join(buffer)
                        last_response_was_confirmation = 0
                    except Exception as join_error:
                        logging.error(f"Error joining buffer: {join_error}")
                        audio_data = None
                else:
                    audio_data = None
                    logging.info(f"{current_phone}: Buffer too small, discarding")
                
                # Xử lý audio
                try:
                    print("========================")
                    print('len_buffer: ',len(buffer))
                    print("========================")
                        
                    result = await process_audio(audio_data, uuid, current_phone)
                    if result == "HANGUP":  # Kiểm tra nếu cuộc gọi đã kết thúc
                        break
                        
                    # Nếu audio_data là None và lần trước đã hỏi xác nhận
                    if audio_data is None and last_response_was_confirmation >= 2:
                        logging.info(f"{current_phone}: Không nhận được phản hồi sau câu hỏi xác nhận, kết thúc cuộc gọi")
                        if await play_goodbye_message(uuid, current_phone) == "HANGUP":
                            break
                    
                    # Cập nhật trạng thái xác nhận
                    if audio_data is None:
                        last_response_was_confirmation += 1
                        
                except Exception as process_error:
                    logging.error(f"Error processing audio: {process_error}")
                
                # Reset trạng thái
                buffer = []
                silence_count = 0
                total_silence_count = 0
                is_buffering = False
                
            elif (not is_buffering) and (total_silence_count > LONG_SILENCE_THRESHOLD):
                result = await process_audio(None, uuid, current_phone)
                if result == "HANGUP":  # Kiểm tra nếu cuộc gọi đã kết thúc
                    break
                
                if last_response_was_confirmation >= 2:
                    logging.info(f"{current_phone}: Không nhận được phản hồi sau câu hỏi xác nhận, kết thúc cuộc gọi")
                    if await play_goodbye_message(uuid, current_phone) == "HANGUP":
                        break
                
                logging.info(f"{current_phone}: Không có phản hồi trong {total_silence_count} frames, hỏi xác nhận.")
                last_response_was_confirmation += 1
                total_silence_count = 0

        except Exception as e:
            logging.error(f"Lỗi trong handle_rtp_stream: {e}")
            break
    
    sock.close()
    logging.info(f"RTP stream ended for {current_phone} (UUID: {uuid}). Stats: {packet_count} packets processed, {speech_frames_detected} speech frames detected, {processing_attempts} processing attempts")
    chatbot.end_conversation()
    
    end_time = time.time()
    duration = end_time - start_time
    data_insert(uuid, current_phone, "CALL DURATION", "", duration)
    
    return 

async def play_welcome_message(uuid, current_phone):
    """Phát thông điệp chào mừng"""
    print('play_welcome_message')
    welcome_file = os.getenv('CONTAINER_WELCOME_FILE') 
    playback_event.set()
    esl_con.execute("playback", welcome_file.replace(os.getenv('CONTAINER_WELCOME_FILE'), os.getenv('WELCOME_FILE')), uuid)
    
    # Tính thời gian của file welcome
    audio = AudioSegment.from_wav(welcome_file)
    playback_duration = len(audio) / 1000.0
    logging.info(f"Playing welcome message for {current_phone}, duration: {playback_duration}s")
    await asyncio.sleep(playback_duration)
    playback_event.clear()

def listen_for_calls(uuid, media_port, sip_from, ch, method):
    """Lắng nghe cuộc gọi từ FreeSWITCH"""
    esl_con.events("plain", "CHANNEL_ANSWER CHANNEL_HANGUP")

    logging.info("Đang lắng nghe cuộc gọi...")
    ch.basic_ack(delivery_tag=method.delivery_tag)
    
    asyncio.run(play_welcome_message(uuid, sip_from))
                    
    asyncio.run(handle_rtp_stream(int(media_port), uuid, sip_from, ch, method))


def process_call(ch, method, properties, body):
    call_data = json.loads(body)
    uuid = call_data["uuid"]
    sip_from = call_data["sip_from"]
    media_port = call_data["media_port"]
    
    logging.info(f"Processing call from {sip_from}, UUID: {uuid}, Port: {media_port}")
    
    # Xử lý audio & chatbot
    listen_for_calls(uuid, media_port, sip_from, ch, method)
    #asyncio.run(handle_rtp_stream(media_port, uuid))
    
    #ch.basic_ack(delivery_tag=method.delivery_tag)    

def start_worker():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv('RABBIT_MQ_HOST')))
    channel = connection.channel()
    channel.queue_declare(queue=os.getenv('RABBIT_MQ_QUEUE'))

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=os.getenv('RABBIT_MQ_QUEUE'), on_message_callback=process_call)
    logging.info("Worker is waiting for messages...")
    
    channel.start_consuming()

if __name__ == "__main__":
    start_worker()
