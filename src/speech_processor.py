import requests
import wave
import io
from config.config import config

class SpeechProcessor:
    def __init__(self):
        self.language = config.STT_LANGUAGE
        self.stt_api_url = "http://localhost:38000/asr/upload/?en=false"  # Thêm URL này vào config nếu cần

    async def speech_to_text(self, audio_data: bytes) -> str:
        try:
            # Chuyển đổi audio data thành định dạng WAV
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(config.AUDIO_CHANNELS)
                wav_file.setsampwidth(2)  # 16-bit audio
                wav_file.setframerate(config.AUDIO_RATE)
                wav_file.writeframes(audio_data)
            
            wav_buffer.seek(0)
            
            # Gửi file audio đến API speech-to-text
            files = {'file': ('audio.wav', wav_buffer, 'audio/wav')}
            response = requests.post(self.stt_api_url, files=files)
            
            if response.status_code == 200:
                result = response.json()
                return result.get('transcription', '')
            else:
                print(f"Lỗi API speech-to-text: {response.status_code}")
                return ''

        except Exception as e:
            print(f"Lỗi khi xử lý speech-to-text: {e}")
            return ''

    async def text_to_speech(self, text: str) -> bytes:
        # Phương thức này không còn cần thiết vì chúng ta đang sử dụng WebSocket
        pass