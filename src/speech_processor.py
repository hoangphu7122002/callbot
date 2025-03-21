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
import os
import random
from pydub import AudioSegment

from dotenv import load_dotenv

# Setup paths and environment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
dotenv_path = os.path.join(ROOT_DIR, ".env")
load_dotenv(dotenv_path)


class SpeechProcessor:
    def __init__(self):
        self.client = None
        if os.getenv("OPENAI_API_KEY"):
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def speech_to_text(self, audio_data: bytes) -> str:
        try:
            if os.getenv("STT_PROVIDER") == "local":
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
            wav_file.setnchannels(int(os.getenv("AUDIO_CHANNELS")))
            wav_file.setsampwidth(int(os.getenv("SAMPLE_WIDTH")))
            wav_file.setframerate(int(os.getenv("AUDIO_RATE")))
            wav_file.writeframes(audio_data)
        
        wav_buffer.seek(0)
        
        # Gửi file audio đến API speech-to-text local
        files = {'file': ('audio.wav', wav_buffer, 'audio/wav')}
        response = requests.post(os.getenv("STT_API_URL"), files=files)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('transcription', '')
        else:
            print(f"Lỗi API speech-to-text local: {response.status_code}")
            return ''

    # async def _openai_speech_to_text(self, audio_data, save_dir="/home/hoangphu7122002/callbot/records"):
    #     """Lưu audio vào thư mục và gửi đến OpenAI"""
    #     try:
    #         uuid = random.randint(1,1000000)
    #         # Đảm bảo thư mục tồn tại
    #         os.makedirs(save_dir, exist_ok=True)

    #         # Định dạng đường dẫn file
    #         audio_filename = f"{save_dir}/asr_debug_{uuid}.wav"

    #         # Lưu file WAV
    #         with wave.open(audio_filename, 'wb') as wav_file:
    #             wav_file.setnchannels(int(os.getenv("AUDIO_CHANNELS")))  # Default 1 kênh
    #             wav_file.setsampwidth(int(os.getenv("SAMPLE_WIDTH")))   # Default 16-bit = 2 bytes
    #             wav_file.setframerate(int(os.getenv("AUDIO_RATE"))) # Default 16kHz
    #             wav_file.writeframes(audio_data)
            
    #         logging.info(f"Audio saved at: {audio_filename}")

    #         # Gửi file đến OpenAI để nhận diện giọng nói
    #         with open(audio_filename, 'rb') as audio_file:
    #             response = self.client.audio.transcriptions.create(
    #                 model=os.getenv("STT_MODEL", "whisper-1"),
    #                 file=audio_file,
    #                 language=os.getenv("STT_LANGUAGE", "vi")
    #             )

    #         return response.text

    #     except Exception as e:
    #         logging.error(f"Error processing audio: {e}")
    #         return None
    
    
    # async def _openai_speech_to_text(self, audio_data, save_dir="/home/hoangphu7122002/callbot/records"):
    #     """Lưu audio vào thư mục, thêm 1s silence trước và sau, rồi gửi đến OpenAI"""
    #     try:
    #         uuid = random.randint(1, 1000000)
    #         os.makedirs(save_dir, exist_ok=True)

    #         # Định dạng đường dẫn file
    #         audio_filename = f"{save_dir}/asr_debug_{uuid}.wav"

    #         # Kiểm tra nếu audio_data là raw PCM, ta phải đóng gói vào WAV
    #         wav_stream = BytesIO()
    #         with wave.open(wav_stream, 'wb') as wav_file:
    #             num_channels = int(os.getenv("AUDIO_CHANNELS", 1))  # Default 1
    #             sample_width = int(os.getenv("SAMPLE_WIDTH", 2))  # Default 16-bit = 2 bytes
    #             frame_rate = int(os.getenv("AUDIO_RATE", 16000))  # Default 16kHz

    #             wav_file.setnchannels(num_channels)
    #             wav_file.setsampwidth(sample_width)
    #             wav_file.setframerate(frame_rate)
    #             wav_file.writeframes(audio_data)  # Ghi dữ liệu raw vào WAV

    #         # Đọc lại WAV từ memory
    #         wav_stream.seek(0)
    #         audio = AudioSegment.from_wav(wav_stream)

    #         # Thêm 1 giây silence trước và sau
    #         silence = AudioSegment.silent(duration=1000)  # 1s
    #         processed_audio = silence + audio + silence

    #         # Xuất file WAV sau khi thêm silence
    #         processed_audio.export(audio_filename, format="wav")
    #         logging.info(f"Processed audio saved at: {audio_filename}")

    #         # Gửi file đến OpenAI
    #         with open(audio_filename, 'rb') as audio_file:
    #             response = self.client.audio.transcriptions.create(
    #                 model=os.getenv("STT_MODEL", "whisper-1"),
    #                 file=audio_file,
    #                 language=os.getenv("STT_LANGUAGE", "vi")
    #             )

    #         return response.text

    #     except Exception as e:
    #         logging.error(f"Error processing audio: {e}")
    #         return None

    async def _openai_speech_to_text(self, audio_data: bytes) -> str:
        try:
            import tempfile
            
            # Tạo temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                with wave.open(temp_wav.name, 'wb') as wav_file:
                    wav_file.setnchannels(int(os.getenv("AUDIO_CHANNELS")))
                    wav_file.setsampwidth(int(os.getenv("SAMPLE_WIDTH")))
                    wav_file.setframerate(int(os.getenv("AUDIO_RATE")))
                    wav_file.writeframes(audio_data)
                
                # Mở file để gửi đến OpenAI
                with open(temp_wav.name, 'rb') as audio_file:
                    response = self.client.audio.transcriptions.create(
                        model=os.getenv("STT_MODEL"),
                        file=audio_file,
                        language=os.getenv("STT_LANGUAGE")
                    )
            
            return response.text
            
        except Exception as e:
            print(f"Lỗi khi sử dụng OpenAI STT: {e}")
            return ''

    async def text_to_speech(self, text, uuid=None):
        """Convert text to speech using configured provider"""
        try:
            if os.getenv("TTS_PROVIDER") == "openai":
                return await self._openai_tts(text)
            elif os.getenv("TTS_PROVIDER") == "local":
                return await self._local_tts(text)
        except Exception as e:
            logging.error(f"Error in text_to_speech: {e}")
            raise

    async def _openai_tts(self, text):
        """Convert text to speech using OpenAI"""
        if not self.client:
            raise Exception("OpenAI client not initialized")
            
        response = self.client.audio.speech.create(
            model=os.getenv("TTS_MODEL"),
            voice=os.getenv("TTS_OPENAI_VOICE"),
            input=text
        )
        return AudioSegment.from_mp3(io.BytesIO(response.content))

    async def _local_tts(self, text):
        """Convert text to speech using local websocket service"""
        sentences = [text]  # Single sentence approach as requested
        
        async with websockets.connect(os.getenv("TTS_WEBSOCKET_URL")) as websocket:
            await websocket.send(json.dumps({
                "text": text,
                "language": os.getenv("TTS_LANGUAGE"),
                "sample_file": os.getenv("TTS_VOICE")
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