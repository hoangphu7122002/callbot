import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import logging
import os
import io
from freeswitchESL import ESL
from pydub import AudioSegment
from threading import Event
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
dotenv_path = os.path.join(ROOT_DIR, ".env")
load_dotenv(dotenv_path)

class PlaybackHandler:
    def __init__(self):
        # Connect to FreeSWITCH ESL
        self.esl_con = ESL.ESLconnection(
            os.getenv('ESL_HOST'), 
            os.getenv('ESL_PORT'), 
            os.getenv('ESL_PASSWORD')
        )
        
        if not self.esl_con.connected():
            raise Exception("Failed to connect to FreeSWITCH")
            
        # Event for tracking playback state
        self.playback_event = Event()
        
        # File paths from environment
        self.welcome_file = os.getenv('WELCOME_FILE')
        self.processing_file = os.getenv('PROCESSING_FILE')
        self.goodbye_file = os.getenv('GOODBYE_FILE')
        self.record_path = os.getenv('RECORD_PATH')
        
    async def play_welcome_message(self, uuid, phone_number):
        """Play the welcome message to the caller."""
        self.playback_event.set()
        try:
            self.esl_con.execute("playback", self.welcome_file, uuid)
            
            # Calculate duration from audio file
            audio = AudioSegment.from_wav(self.welcome_file)
            playback_duration = len(audio) / 1000.0
            
            logging.info(f"Playing welcome message for {phone_number}, duration: {playback_duration}s")
            await asyncio.sleep(playback_duration)
            
            return True
        except Exception as e:
            logging.error(f"Error playing welcome message: {e}")
            return False
        finally:
            self.playback_event.clear()
            
    async def play_processing_message(self, uuid, phone_number):
        """Play the processing message while waiting for a response."""
        try:
            self.esl_con.execute("playback", self.processing_file, uuid)
            
            # Calculate duration from audio file
            audio = AudioSegment.from_wav(self.processing_file)
            playback_duration = len(audio) / 1000.0
            
            logging.info(f"Playing processing message for {phone_number}, duration: {playback_duration}s")
            await asyncio.sleep(playback_duration)
            
            return True
        except Exception as e:
            logging.error(f"Error playing processing message: {e}")
            return False
            
    async def play_goodbye_message(self, uuid, phone_number):
        """Play the goodbye message and end the call."""
        self.playback_event.set()
        try:
            self.esl_con.execute("playback", self.goodbye_file, uuid)
            
            # Calculate duration from audio file
            audio = AudioSegment.from_wav(self.goodbye_file)
            playback_duration = len(audio) / 1000.0
            
            logging.info(f"Playing goodbye message for {phone_number}, duration: {playback_duration}s")
            await asyncio.sleep(playback_duration)
            
            # End the call
            self.esl_con.api("uuid_kill", uuid)
            return "HANGUP"
        except Exception as e:
            logging.error(f"Error playing goodbye message: {e}")
            return False
        finally:
            self.playback_event.clear()
            
    async def play_response(self, uuid, phone_number, audio_data, filename=None):
        """Play an audio response to the caller."""
        try:
            if filename is None:
                filename = f"response_{uuid}.wav"
            
            # Ensure record_path exists
            if not os.path.exists(self.record_path):
                try:
                    os.makedirs(self.record_path, exist_ok=True)
                    logging.info(f"Created record path directory: {self.record_path}")
                except Exception as e:
                    logging.warning(f"Failed to create record path: {e}")
                    # Use a fallback path in current directory
                    self.record_path = os.path.join(os.getcwd(), "records")
                    os.makedirs(self.record_path, exist_ok=True)
                    logging.info(f"Using fallback path: {self.record_path}")
                
            output_file = os.path.join(self.record_path, filename)
            
            # Convert and save audio
            audio_segment = AudioSegment.from_mp3(io.BytesIO(audio_data))
            audio_segment.export(output_file, format='wav')
            
            # Log file creation for debugging
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                logging.info(f"Created response file: {output_file}, size: {file_size} bytes")
            else:
                logging.warning(f"Failed to create response file: {output_file}")
            
            # Disable DTMF during playback
            self.esl_con.execute("uuid_setvar", f"{uuid} playback_terminators none")
            
            # Play the audio
            self.esl_con.execute("playback", output_file, uuid)
            
            # Wait for playback to complete
            audio_duration = len(audio_segment) / 1000.0
            logging.info(f"Playing response for {phone_number}, duration: {audio_duration}s")
            await asyncio.sleep(audio_duration + 0.2)  # Add small buffer
            
            return audio_duration
        except Exception as e:
            logging.error(f"Error playing response: {e}")
            return 0
            
    async def check_hangup(self, uuid, phone_number):
        """Check if the call has been hung up."""
        try:
            e = self.esl_con.recvEventTimed(1)  # 1 second timeout
            if e:
                event_name = e.getHeader("Event-Name")
                if event_name == "CHANNEL_HANGUP":
                    current_uuid = e.getHeader("Unique-ID")
                    if current_uuid == uuid:
                        logging.info(f"Call hangup detected: {uuid} ({phone_number})")
                        return "HANGUP"
            return None
        except Exception as e:
            logging.error(f"Error checking hangup: {e}")
            return None
            
    def is_playback_active(self):
        """Check if playback is currently active."""
        return self.playback_event.is_set()
        
    def set_playback_active(self, active=True):
        """Set the playback active state."""
        if active:
            self.playback_event.set()
        else:
            self.playback_event.clear()
            
    def stop_hold_music(self, uuid):
        """Stop any hold music or similar audio."""
        try:
            self.esl_con.api("uuid_break", uuid)
            return True
        except Exception as e:
            logging.error(f"Error stopping hold music: {e}")
            return False 