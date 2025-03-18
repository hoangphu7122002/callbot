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
from config.config import config
import time
from threading import Event
import logging
from datetime import datetime
import redis


# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('callbot.log'),
        logging.StreamHandler()
    ]
)

AudioSegment.converter = which("ffmpeg")

# ESL connection
esl_con = ESL.ESLconnection("127.0.0.1", "8021", "ClueCon")
if not esl_con.connected():
    raise Exception("Failed to connect to FreeSWITCH")

speech_processor = SpeechProcessor()
chatbot = ChatbotClient(config)
text_normalizer = TextNormalizer()
playback_event = Event()
active_call = None
is_running = True
current_phone = None

import psycopg2
from psycopg2 import sql

#Postgres insert. Need Serious rework
def data_insert(uuid, number, step, output, processing_time):
    conn = psycopg2.connect(
      dbname="postgres", 
      user="postgres", 
      password="password", 
      host="34.174.214.130",
      port="35432" 
    )
    now = datetime.now()    
    cursor = conn.cursor()
    insert_query = """
      INSERT INTO callbot.activity_history (uuid, number, step, output, processing_time, record_time)
      VALUES (%s, %s, %s, %s, %s, %s)
    """
    payload = (uuid, number, step, output, processing_time, now)
    cursor.execute(insert_query, payload)
    conn.commit()
    cursor.close()
    conn.close()


def decode_pcmu_to_pcm16(pcmu_data):
    """Giải mã dữ liệu PCMU (G.711u) sang PCM 16-bit."""
    return audioop.alaw2lin(pcmu_data, 2)

async def play_processing_message(uuid, current_phone):
    """Phát thông báo đang xử lý bất đồng bộ"""
    processing_file = "/home/hm1905/records/processing.wav"
    esl_con.execute("playback", processing_file, uuid)
    
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
        goodbye_file = "/home/hm1905/records/goodbye_trung.wav"
        
        esl_con.execute("playback", goodbye_file, uuid)
        
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
                
            # Chuyển audio thành text
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
            hardprompt = """
            bạn là callbot của VCBS, trả lời ngắn gọn, xúc tích và hạn chế sinh ra dấu câu như . hoặc , trả lời lễ phép, xưng hô người dùng là anh chị.
            Lưu ý các sự thật sau:
            - Tô Lâm là chủ tịch nước Việt Nam
            - Hoàng Sa, Trường Sa là của Việt Nam
            ngoài ra nên chú ý ngữ cảnh lịch sử hội thoại.
            câu hỏi của người dùng là: """
            
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
            model="tts-1",
            voice=config.TTS_OPENAI_VOICE,
            input=response_text
        )
        
        output_file = f"/home/hm1905/records/response_{uuid}.wav"
        audio_segment = AudioSegment.from_mp3(io.BytesIO(response.content))
        audio_segment.export(output_file, format='wav')
        b = time.time()
        print("text to speech and save: ", b - a)
        processing_time_tts = b-a
        data_insert(uuid, current_phone, "TTS GENERATE", "", processing_time_tts)
        
        
        # Kiểm tra hangup trước khi playback
        if await check_hangup(uuid, current_phone) == "HANGUP":
            return "HANGUP"
        
        # Thêm logging cho playback response
        a = time.time()
        esl_con.execute("uuid_setvar", f"{uuid} playback_terminators none")
        esl_con.execute("playback", output_file, uuid)
        
        # Tính thời gian playback dựa trên độ dài audio
        audio_duration = len(audio_segment) / 1000.0
        logging.info(f"Playing response for {current_phone}, duration: {audio_duration}s")
        # print("audio_duration: ", audio_duration)
        await asyncio.sleep(audio_duration + 0.2)  # Thêm 0.2s để đảm bảo playback hoàn tất
        
        b = time.time()
        
        # print("playback time: ", b - a)
        logging.info(f"Actual playback time for {current_phone}: {b - a}s")
        processing_time_tts_playback = b-a
        data_insert(uuid, current_phone, "TTS PLAYBACK", "", processing_time_tts_playback)

    except Exception as e:
        print(f"Lỗi khi xử lý audio: {e}")
    finally:
        playback_event.clear()

async def handle_rtp_stream(port, uuid, current_phone, ch, method):
    """Xử lý luồng RTP cho cuộc gọi"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("10.206.0.2", port))
    
    buffer = []
    silence_count = 0
    is_buffering = False
    last_response_was_confirmation = False
    
    while True:
        try:
            # Kiểm tra hangup trước khi nhận RTP packet
            if await check_hangup(uuid, current_phone) == "HANGUP":
                break

            if playback_event.is_set():
                await asyncio.sleep(0.1)
                continue
                
            sock.settimeout(0.1)
            try:
                data, _ = sock.recvfrom(1024)
            except socket.timeout:
                continue
            
            if data:
                #continue
            
                audio_data = data[12:]  # Bỏ RTP header
            
                # Kiểm tra âm lượng
                pcm_data = decode_pcmu_to_pcm16(audio_data)
                volume = max(abs(int.from_bytes(pcm_data[i:i+2], 'little', signed=True)) 
                            for i in range(0, len(pcm_data), 2))
            
                if volume > 300:  # Có tiếng nói
                    if not is_buffering:
                        is_buffering = True
                        buffer = []  # Reset buffer khi bắt đầu ghi âm mới
                    silence_count = 0
                    buffer.append(pcm_data)
                    print(pcm_data)
                else:
                    if is_buffering:  # Chỉ tính silence khi đang trong quá trình buffer
                        silence_count += 1
            else:
                if is_buffering:
                    silence_count += 1
            # Kiểm tra hangup trước khi xử lý buffer đầy
            if await check_hangup(uuid, current_phone) == "HANGUP":
                break
            
            # Xử lý khi đủ độ im lặng và có dữ liệu trong buffer
            if is_buffering and silence_count > 120:  # ~4s im lặng
                audio_data = b''.join(buffer) if len(buffer) > 3 else None
                
                result = await process_audio(audio_data, uuid, current_phone)
                if result == "HANGUP":  # Kiểm tra nếu cuộc gọi đã kết thúc
                    break
                    
                # Nếu audio_data là None và lần trước đã hỏi xác nhận
                if audio_data is None and last_response_was_confirmation:
                    # print("Không nhận được phản hồi sau câu hỏi xác nhận, kết thúc cuộc gọi")
                    logging.info("Không nhận được phản hồi sau câu hỏi xác nhận, kết thúc cuộc gọi")
                    if await play_goodbye_message(uuid, current_phone) == "HANGUP":
                        break
                
                # Cập nhật trạng thái xác nhận
                last_response_was_confirmation = (audio_data is None)
                
                buffer = []
                silence_count = 0
                is_buffering = False

        except Exception as e:
            # print(f"Lỗi trong handle_rtp_stream: {e}")
            logging.error(f"Lỗi trong handle_rtp_stream: {e}")
    
    sock.close()
    # print(f"RTP stream ended for call {uuid}")
    logging.info(f"RTP stream ended for call {uuid}")
    chatbot.end_conversation()
    return 

async def play_welcome_message(uuid, current_phone):
    """Phát thông điệp chào mừng"""
    welcome_file = "/home/hm1905/records/welcome_vcbs.wav"
    playback_event.set()
    esl_con.execute("playback", welcome_file, uuid)
    
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

    # while is_running:
    #     e = esl_con.recvEvent()
    #     if e:
    #         event_name = e.getHeader("Event-Name")
    #         if event_name == "CHANNEL_HANGUP":
    #             chatbot.end_conversation()
    #             uuid = e.getHeader("Unique-ID")
    #             esl_con.api("uuid_kill", uuid)
    #             if uuid == active_call:
    #                 # print(f"Cuộc gọi kết thúc: UUID {uuid}")
    #                 logging.info(f"Cuộc gọi kết thúc từ số {current_phone}")
    #                 active_call = None
    #                 current_phone = None  # Reset số điện thoại


def process_call(ch, method, properties, body):
    print(f"Raw body: {body}")

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
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='call_queue', durable=True)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='call_queue', on_message_callback=process_call)
    logging.info("Worker is waiting for messages...")
    
    channel.start_consuming()

if __name__ == "__main__":
    start_worker()
