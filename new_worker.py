#!/usr/bin/env python3
import json
import time
import logging
import asyncio
import socket
import io
import os
from datetime import datetime
from dotenv import load_dotenv
from src.speech_processor import SpeechProcessor
from src.chatbot_client import ChatbotClient
from src.text_normalizer import TextNormalizer
from src.vad_processor import VADProcessor
from src.playback_handler import PlaybackHandler
from src.db_handler import DBHandler
from src.queue_handler import QueueHandler

# Load environment variables
load_dotenv()

# Configure logging
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

# Constants
SILENCE_FRAMES_THRESHOLD = int(os.getenv('SILENCE_FRAMES', '60'))
LONG_SILENCE_THRESHOLD = int(os.getenv('LONG_SILENCE_THRESHOLD', '250'))
MIN_BUFFER_SIZE = int(os.getenv('MIN_BUFFER_SIZE', '15'))

# Initialize components
speech_processor = SpeechProcessor()
chatbot = ChatbotClient()
text_normalizer = TextNormalizer()
vad_processor = VADProcessor()
playback_handler = PlaybackHandler()
# Worker primarily needs PostgreSQL for call activity logging
db_handler = DBHandler(init_postgres=True, init_redis=False, init_minio=False)
queue_handler = QueueHandler()

# Global variables for state tracking
active_call = None
is_running = True
current_phone = None
start_time = None

async def process_audio(audio_data, uuid, phone_number):
    """Process audio data and generate response."""
    try:
        playback_handler.set_playback_active(True)
        
        async def main_processing():
            # Handle empty audio (silence)
            if audio_data is None:
                confirmation_text = "anh chị có cần gì nữa không ạ"
                logging.info(f"Bot to {phone_number} (silence prompt): {confirmation_text}")
                return confirmation_text
                
            # Speech-to-text
            a = time.time()
            user_text = await speech_processor.speech_to_text(audio_data)
            b = time.time()
            processing_time_asr = b - a
            db_handler.insert_call_activity(uuid, phone_number, "ASR", user_text, processing_time_asr)
            logging.info(f"Speech to text time: {b - a}s")
            
            # Check for hangup
            if await playback_handler.check_hangup(uuid, phone_number) == "HANGUP":
                return "HANGUP"
            
            if not user_text:
                return None
                
            logging.info(f"User {phone_number}: {user_text}")
            
            # Check for end conversation keywords
            if chatbot.should_end_conversation(user_text.lower()) or user_text.lower() == "không" or user_text.lower() == "xong":
                logging.info(f"End conversation keyword detected from {phone_number}: {user_text}")
                return await playback_handler.play_goodbye_message(uuid, phone_number)
            
            # Get chatbot response
            a = time.time()
            hardprompt = os.getenv('HARD_PROMPT')
            bot_response = await chatbot.get_response(hardprompt + user_text)
            
            # Check if response indicates conversation should end
            bot_response, flag = text_normalizer.check_end_conversation(bot_response)
            if flag == True:
                logging.info(f"End conversation detected in bot response to {phone_number}")
                return await playback_handler.play_goodbye_message(uuid, phone_number)
            
            # Normalize and log response
            normalized_response = text_normalizer.normalize_vietnamese_text(bot_response)
            b = time.time()
            processing_time_llm = b - a
            db_handler.insert_call_activity(uuid, phone_number, "LLM", normalized_response, processing_time_llm)
            logging.info(f"LLM answer time: {b - a}s")
            logging.info(f"Bot response to {phone_number}: {normalized_response}")
            
            # Check for hangup
            if await playback_handler.check_hangup(uuid, phone_number) == "HANGUP":
                return "HANGUP"
            
            return normalized_response

        # Run processing message in parallel with main processing when audio exists
        if audio_data:
            processing_task = asyncio.create_task(playback_handler.play_processing_message(uuid, phone_number))
            main_task = asyncio.create_task(main_processing())
            
            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [processing_task, main_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Handle task completion
            if processing_task in done:
                response_text = await main_task
            else:
                processing_task.cancel()
                try:
                    await processing_task
                except asyncio.CancelledError:
                    pass
                response_text = main_task.result()
        else:
            # Just run main processing if no audio
            response_text = await main_processing()

        if not response_text:
            return
            
        if response_text == "HANGUP":
            return "HANGUP"

        # Check for hangup before TTS
        if await playback_handler.check_hangup(uuid, phone_number) == "HANGUP":
            return "HANGUP"
            
        # Text-to-speech conversion
        a = time.time()
        response = chatbot.client.audio.speech.create(
            model=os.getenv("TTS_MODEL"),
            voice=os.getenv("TTS_OPENAI_VOICE"),
            input=response_text
        )
        
        # Play response
        b = time.time()
        processing_time_tts = b - a
        db_handler.insert_call_activity(uuid, phone_number, "TTS", "", processing_time_tts)
        logging.info(f"Text to speech time: {b - a}s")
        
        # Check for hangup before playback
        if await playback_handler.check_hangup(uuid, phone_number) == "HANGUP":
            return "HANGUP"
        
        # Play the response
        a = time.time()
        audio_duration = await playback_handler.play_response(uuid, phone_number, response.content)
        b = time.time()
        
        processing_time_playback = b - a
        db_handler.insert_call_activity(uuid, phone_number, "PLAYBACK", "", processing_time_playback)
        logging.info(f"Playback time: {b - a}s")
        
    except Exception as e:
        logging.error(f"Error processing audio: {e}")
    finally:
        playback_handler.set_playback_active(False)

async def handle_rtp_stream(port, uuid, phone_number, ch, method):
    """Handle an RTP stream for a call."""
    # Create UDP socket to receive RTP packets
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((os.getenv('RTP_HOST'), int(port)))
    
    logging.info(f"RTP Stream started for {phone_number} on port {port}")
    
    # State variables
    buffer = []
    silence_count = 0
    is_buffering = False
    last_response_was_confirmation = 0
    
    # Statistics for logging
    global start_time
    start_time = time.time()
    packet_count = 0
    speech_frames_detected = 0
    processing_attempts = 0
    total_silence_count = 0
    
    try:
        while True:
            # Check for hangup
            if await playback_handler.check_hangup(uuid, phone_number) == "HANGUP":
                logging.info(f"Hangup detected for {phone_number}, ending RTP stream")
                break

            # Skip processing if playback is active
            if playback_handler.is_playback_active():
                await asyncio.sleep(0.1)
                continue
                
            # Receive RTP packet
            sock.settimeout(0.1)
            try:
                data, _ = sock.recvfrom(1024)
                packet_count += 1
                if packet_count % 500 == 0:
                    logging.debug(f"Processed {packet_count} RTP packets, detected {speech_frames_detected} speech frames")
            except socket.timeout:
                continue
            
            if data:
                # Extract audio data from RTP packet (skip 12-byte RTP header)
                audio_data = data[12:]
                
                # Process audio frame to detect speech
                speech_detected, pcm_data_clean, max_volume = vad_processor.process_audio_frame(audio_data)
                
                # Update counters based on speech detection
                if speech_detected:
                    speech_frames_detected += 1
                    if not is_buffering:
                        is_buffering = True
                        buffer = []  # Reset buffer for new recording
                        logging.info(f"{phone_number} on port {port}: Speech detected, buffering started")
                    silence_count = 0
                    buffer.append(pcm_data_clean)
                    print(pcm_data_clean)
                else:
                    if is_buffering:
                        silence_count += 1
                        if silence_count % 10 == 0:
                            logging.debug(f"Silence count: {silence_count}/{SILENCE_FRAMES_THRESHOLD}, buffer size: {len(buffer)}")
                    total_silence_count += 1
            else:
                if is_buffering:
                    silence_count += 1
                total_silence_count += 1
                
            # Check for hangup
            if await playback_handler.check_hangup(uuid, phone_number) == "HANGUP":
                break
                
            # Process audio when either:
            # 1. We were buffering and silence is long enough
            # 2. Long silence with no buffering (generate confirmation prompt)
            
            # Case 1: End of speech detected
            if is_buffering and silence_count > SILENCE_FRAMES_THRESHOLD:
                processing_attempts += 1
                logging.info(f"{phone_number}: Speech segment completed, processing audio (attempt #{processing_attempts})")
                
                # Process only if buffer has enough data
                if buffer and len(buffer) > MIN_BUFFER_SIZE:
                    try:
                        audio_data = b''.join(buffer)
                        last_response_was_confirmation = 0
                    except Exception as join_error:
                        logging.error(f"Error joining buffer: {join_error}")
                        audio_data = None
                else:
                    audio_data = None
                    logging.info(f"{phone_number}: Buffer too small, discarding")
                
                # Process the audio
                result = await process_audio(audio_data, uuid, phone_number)
                if result == "HANGUP":
                    break
                    
                # Check if we need to end call due to lack of response
                if audio_data is None and last_response_was_confirmation >= 2:
                    logging.info(f"{phone_number}: No response after confirmation question, ending call")
                    if await playback_handler.play_goodbye_message(uuid, phone_number) == "HANGUP":
                        break
                
                # Update confirmation counter
                if audio_data is None:
                    last_response_was_confirmation += 1
                    
                # Reset state
                buffer = []
                silence_count = 0
                total_silence_count = 0
                is_buffering = False
            
            # Case 2: Long silence without active speech
            elif (not is_buffering) and (total_silence_count > LONG_SILENCE_THRESHOLD):
                result = await process_audio(None, uuid, phone_number)
                if result == "HANGUP":
                    break
                
                # End call if multiple confirmations without response
                if last_response_was_confirmation >= 2:
                    logging.info(f"{phone_number}: No response after confirmation question, ending call")
                    if await playback_handler.play_goodbye_message(uuid, phone_number) == "HANGUP":
                        break
                
                logging.info(f"{phone_number}: Long silence detected ({total_silence_count} frames), asking confirmation")
                last_response_was_confirmation += 1
                total_silence_count = 0

    except Exception as e:
        logging.error(f"Error in handle_rtp_stream: {e}")
    finally:
        # Clean up
        sock.close()
        logging.info(f"RTP stream ended for {phone_number} (UUID: {uuid}). Stats: {packet_count} packets, {speech_frames_detected} speech frames, {processing_attempts} processing attempts")
        chatbot.end_conversation()
        
        # Record call duration
        end_time = time.time()
        duration = end_time - start_time
        db_handler.insert_call_activity(uuid, phone_number, "CALL DURATION", "", duration)

def process_call(ch, method, properties, body):
    """Process an incoming call from the queue."""
    try:
        # Parse call data
        try:
            call_data = json.loads(body)
        except json.JSONDecodeError:
            # If body is already a dictionary (e.g., if it was loaded previously)
            if isinstance(body, dict):
                call_data = body
            else:
                logging.error(f"Failed to parse message body as JSON: {body}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
                
        uuid = call_data["uuid"]
        phone_number = call_data["sip_from"]
        media_port = call_data["media_port"]
        
        logging.info(f"Processing call from {phone_number}, UUID: {uuid}, Port: {media_port}")
        
        # Acknowledge message immediately
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
        # Play welcome message and handle RTP stream
        asyncio.run(playback_handler.play_welcome_message(uuid, phone_number))
        asyncio.run(handle_rtp_stream(int(media_port), uuid, phone_number, ch, method))
        
    except Exception as e:
        logging.error(f"Error processing call: {e}")
        # Still acknowledge to prevent the message from being requeued
        if not ch.is_closed:
            ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    """Main function to start the worker."""
    try:
        # Reset VAD state
        vad_processor.reset_state()
        
        # Start consuming from the queue
        queue_handler.start_consuming(process_call)
        
    except KeyboardInterrupt:
        logging.info("Worker stopped by user")
    except Exception as e:
        logging.error(f"Error in worker: {e}")
    finally:
        # Close connections
        queue_handler.stop_consuming()

if __name__ == "__main__":
    main() 