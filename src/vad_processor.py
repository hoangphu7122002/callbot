import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import webrtcvad
import audioop
import numpy as np
import noisereduce as nr
import logging
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
dotenv_path = os.path.join(ROOT_DIR, ".env")
load_dotenv(dotenv_path)

class VADProcessor:
    def __init__(self):
        load_dotenv()
        
        # Audio configuration for WebRTC VAD
        self.SAMPLE_RATE = int(os.getenv('AUDIO_RATE'))
        self.FRAME_DURATION_MS = int(os.getenv('FRAME_DURATION_MS'))
        self.FRAME_SIZE = int(self.SAMPLE_RATE * self.FRAME_DURATION_MS / 1000) * 2  # 2 bytes/sample

        # VAD configuration
        self.VAD_MODE = int(os.getenv('VAD_MODE'))  # 0: least aggressive, 3: most aggressive
        self.vad = webrtcvad.Vad(self.VAD_MODE)
        
        # Speech detection configuration
        self.MIN_VOLUME_THRESHOLD = int(os.getenv('MIN_VOLUME', '500'))
        self.SPEECH_VOLUME_THRESHOLD = int(os.getenv('SPEECH_VOLUME', '800'))
        self.SILENCE_FRAMES_THRESHOLD = int(os.getenv('SILENCE_FRAMES', '60'))
        self.LONG_SILENCE_THRESHOLD = int(os.getenv('LONG_SILENCE_THRESHOLD', '250'))
        self.MIN_BUFFER_SIZE = int(os.getenv('MIN_BUFFER_SIZE', '15'))
        
        # Noise reduction configuration
        self.ENABLE_NOISE_REDUCTION = os.getenv('ENABLE_NOISE_REDUCTION', 'true').lower() == 'true'
        
        logging.info(f"VAD initialized with mode: {self.VAD_MODE}, Sample rate: {self.SAMPLE_RATE}, "
                     f"Min volume: {self.MIN_VOLUME_THRESHOLD}, Speech volume: {self.SPEECH_VOLUME_THRESHOLD}")
        logging.info("=======================test=======================")
    def frame_generator(self, frame_duration_ms, audio, sample_rate):
        """Split audio data into fixed-length frames."""
        n = int(sample_rate * frame_duration_ms / 1000) * 2  # bytes per frame
        offset = 0
        while offset + n <= len(audio):
            yield audio[offset:offset+n]
            offset += n

    def apply_noise_suppression(self, pcm_data, sample_rate=None):
        """Apply noise suppression with noisereduce library."""
        if sample_rate is None:
            sample_rate = self.SAMPLE_RATE
            
        # Skip noise reduction if disabled or data too short
        if not self.ENABLE_NOISE_REDUCTION or len(pcm_data) < 1000:
            return pcm_data
            
        try:
            # Convert bytes to numpy array in float32 format
            audio_np = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
            
            if len(audio_np) == 0:
                return pcm_data
            
            try:
                reduced_noise = nr.reduce_noise(
                    y=audio_np, 
                    sr=sample_rate,
                    prop_decrease=float(os.getenv('PROP_DECREASE', '0.75'))
                )
                return reduced_noise.astype(np.int16).tobytes()
            except Exception as inner_e:
                logging.error(f"Error in noise reduction algorithm: {inner_e}")
                return pcm_data
                
        except Exception as e:
            logging.error(f"Error in noise suppression: {e}")
            return pcm_data

    def decode_pcmu_to_pcm16(self, pcmu_data):
        """Decode PCMU (G.711u) data to PCM 16-bit."""
        try:
            # Check input data
            if not pcmu_data or len(pcmu_data) < 2:
                return b''
                
            # Decode PCMU to PCM 16-bit
            pcm_data = audioop.alaw2lin(pcmu_data, 2)
            
            try:
                # Convert sample rate if needed for WebRTC VAD
                if abs(self.SAMPLE_RATE - 8000) > 100:
                    pcm_data = audioop.ratecv(pcm_data, 2, 1, 8000, self.SAMPLE_RATE, None)[0]
            except Exception as rate_error:
                logging.error(f"Sample rate conversion error: {rate_error}")
            
            return pcm_data
        except Exception as e:
            logging.error(f"Error decoding PCMU to PCM16: {e}")
            return b''

    def process_audio_frame(self, pcmu_data):
        """Process an RTP audio frame and determine if it contains speech.
        
        Returns:
            tuple: (is_speech_detected, clean_pcm_data, max_volume)
        """
        # Decode PCMU to PCM16
        pcm_data = self.decode_pcmu_to_pcm16(pcmu_data)
        if not pcm_data:
            return False, b'', 0
            
        # Apply noise suppression
        # pcm_data_clean = self.apply_noise_suppression(pcm_data)
        pcm_data_clean = pcm_data
        
        # Check for speech - simplified direct detection without consecutive frames tracking
        speech_detected = False
        max_volume = 0
        
        try:
            # Calculate maximum volume
            if len(pcm_data) >= 2:
                for i in range(0, len(pcm_data) - 1, 2):
                    volume = abs(int.from_bytes(pcm_data[i:i+2], 'little', signed=True))
                    if volume > max_volume:
                        max_volume = volume
                        
            # Only process VAD if volume is above minimum threshold
            if max_volume > self.MIN_VOLUME_THRESHOLD:
                # Split data into frames
                frames = list(self.frame_generator(self.FRAME_DURATION_MS, pcm_data_clean, self.SAMPLE_RATE))
                valid_frames = [frame for frame in frames if len(frame) == self.FRAME_SIZE]
                
                # Check valid frames for speech - simplified logic
                if valid_frames:
                    # Count speech frames
                    speech_frames = 0
                    for frame in valid_frames:
                        try:
                            if self.vad.is_speech(frame, self.SAMPLE_RATE):
                                speech_frames += 1
                        except Exception as frame_error:
                            logging.debug(f"Error checking frame: {frame_error}")
                            continue
                    
                    # Detect speech if at least one frame has speech and volume is above threshold
                    speech_detected = (speech_frames > 0) and (max_volume > self.SPEECH_VOLUME_THRESHOLD)
                else:
                    # Use simple volume-based detection if no valid frames
                    speech_detected = max_volume > self.SPEECH_VOLUME_THRESHOLD * 1.5
            else:
                speech_detected = False
            
        except Exception as e:
            logging.error(f"VAD error: {e}")
            # Fallback to simpler volume-based detection
            try:
                speech_detected = max_volume > self.SPEECH_VOLUME_THRESHOLD
            except Exception as inner_e:
                logging.error(f"Fallback detection error: {inner_e}")
                speech_detected = False
        
        return speech_detected, pcm_data_clean, max_volume
        
    def reset_state(self):
        """Reset the internal state of the VAD processor."""
        # No state to reset anymore since we removed consecutive_speech_frames
        pass 