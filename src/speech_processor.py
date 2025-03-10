import requests
import wave
import io
import json
import base64
from io import BytesIO
import websockets
from pydub import AudioSegment
import logging
from openai import OpenAI
from config.config import config

class SpeechProcessor:
    def __init__(self):
        self.language = config.STT_LANGUAGE
        self.stt_api_url = config.STT_API_URL
        self.client = None
        if hasattr(config, 'OPENAI_API_KEY'):
            self.client = OpenAI(api_key=config.OPENAI_API_KEY)

    async def speech_to_text(self, audio_data: bytes) -> str:
        try:
            if config.STT_PROVIDER == "local":
                return await self._local_speech_to_text(audio_data)
            else:
                return await self._openai_speech_to_text(audio_data)
        except Exception as e:
            print(f"Lỗi khi xử lý speech-to-text: {e}")
            return ''

    async def _local_speech_to_text(self, audio_data: bytes) -> str:
        # Chuyển đổi audio data thành định dạng WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(config.AUDIO_CHANNELS)
            wav_file.setsampwidth(2)
            wav_file.setframerate(config.AUDIO_RATE)
            wav_file.writeframes(audio_data)
        
        wav_buffer.seek(0)
        
        # Gửi file audio đến API speech-to-text local
        files = {'file': ('audio.wav', wav_buffer, 'audio/wav')}
        response = requests.post(self.stt_api_url, files=files)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('transcription', '')
        else:
            print(f"Lỗi API speech-to-text local: {response.status_code}")
            return ''

    async def _openai_speech_to_text(self, audio_data: bytes) -> str:
        try:
            import tempfile
            
            # Tạo temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                print("===============")
                print(temp_wav.name)
                print("===============")
                with wave.open(temp_wav.name, 'wb') as wav_file:
                    wav_file.setnchannels(config.AUDIO_CHANNELS)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(config.AUDIO_RATE)
                    wav_file.writeframes(audio_data)
                
                # Mở file để gửi đến OpenAI
                with open(temp_wav.name, 'rb') as audio_file:
                    response = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=config.STT_LANGUAGE
                    )
            
            return response.text
            
        except Exception as e:
            print(f"Lỗi khi sử dụng OpenAI STT: {e}")
            return ''

    async def text_to_speech(self, text, uuid=None):
        """Convert text to speech using configured provider"""
        try:
            if config.TTS_PROVIDER == "openai":
                return await self._openai_tts(text)
            elif config.TTS_PROVIDER == "local":
                return await self._local_tts(text)
        except Exception as e:
            logging.error(f"Error in text_to_speech: {e}")
            raise

    async def _openai_tts(self, text):
        """Convert text to speech using OpenAI"""
        if not self.client:
            raise Exception("OpenAI client not initialized")
            
        response = self.client.audio.speech.create(
            model="tts-1",
            voice=config.TTS_OPENAI_VOICE,
            input=text
        )
        return AudioSegment.from_mp3(io.BytesIO(response.content))

    async def _local_tts(self, text):
        """Convert text to speech using local websocket service"""
        sentences = [text]  # Single sentence approach as requested
        
        async with websockets.connect(config.TTS_WEBSOCKET_URL) as websocket:
            await websocket.send(json.dumps({
                "text": text,
                "language": config.TTS_LANGUAGE,
                "sample_file": config.TTS_VOICE
            }))
            
            combined_audio = AudioSegment.empty()
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                
                if "error" in data:
                    logging.error(f"TTS Error: {data['error']}")
                    continue
                    
                if "audio_base64" in data:
                    audio_bytes = base64.b64decode(data["audio_base64"])
                    segment = AudioSegment.from_wav(BytesIO(audio_bytes))
                    combined_audio += segment
                    
                if data["index"] == data["total"] - 1:
                    break
                    
        return combined_audio
