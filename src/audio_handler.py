import pyaudio
import numpy as np
import wave
from array import array
import io
from openai import OpenAI
from config.config import config
from pydub import AudioSegment
import tempfile

class AudioHandler:
    def __init__(self, chunk=1024, channels=1, rate=16000, 
                 silence_threshold=300, silence_chunks=100, 
                 initial_silence_chunks=80):
        self.CHUNK = chunk
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = channels
        self.RATE = rate
        self.SILENCE_THRESHOLD = silence_threshold
        self.SILENCE_CHUNKS = silence_chunks
        self.INITIAL_SILENCE_CHUNKS = initial_silence_chunks
        self.p = pyaudio.PyAudio()
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)

    def record_audio(self):
        stream = self.p.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )

        print("* Đang lắng nghe...")
        frames = []
        silent_chunks = 0
        has_speech = False
        max_volume = 0

        while True:
            try:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                array_data = array('h', data)
                
                volume = sum(abs(x) for x in array_data) / len(array_data)
                max_volume = max(max_volume, volume)
                
                # In thông tin âm lượng khi vượt ngưỡng hoặc mỗi 20 chunk
                # if volume > self.SILENCE_THRESHOLD or silent_chunks % 20 == 0:
                #     print(f"Âm lượng hiện tại: {volume:.2f}, Ngưỡng: {self.SILENCE_THRESHOLD}")

                if volume > self.SILENCE_THRESHOLD:
                    silent_chunks = 0
                    has_speech = True
                    frames.append(data)
                else:
                    silent_chunks += 1
                    if has_speech:
                        frames.append(data)

                if has_speech and silent_chunks > self.SILENCE_CHUNKS:
                    print(f"Dừng ghi âm: {silent_chunks} chunk im lặng sau tiếng nói")
                    break
                elif not has_speech and silent_chunks > self.INITIAL_SILENCE_CHUNKS:
                    print(f"Không phát hiện tiếng nói sau {silent_chunks} chunk")
                    print(f"Âm lượng tối đa: {max_volume:.2f}, Ngưỡng: {self.SILENCE_THRESHOLD}")
                    stream.stop_stream()
                    stream.close()
                    return None

            except Exception as e:
                print(f"Lỗi khi ghi âm: {e}")
                break

        stream.stop_stream()
        stream.close()

        if has_speech and len(frames) > 0:
            return b''.join(frames)
        return None

    def play_audio(self, audio_data):
        if config.TTS_PROVIDER == "local":
            self._play_local_audio(audio_data)
        else:
            self._play_openai_audio(audio_data)

    def _play_local_audio(self, audio_data):
        stream = self.p.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            output=True
        )
        
        if isinstance(audio_data, bytes):
            stream.write(audio_data)
        else:
            stream.write(audio_data.read())
            
        stream.stop_stream()
        stream.close()

    def _play_openai_audio(self, text_input):
        try:
            # Đảm bảo input là text
            if not isinstance(text_input, str):
                if hasattr(text_input, 'read'):
                    text_input = text_input.read().decode('utf-8')
                else:
                    text_input = text_input.decode('utf-8')

            # Gọi API OpenAI TTS
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=config.TTS_OPENAI_VOICE,
                input=text_input
            )
            
            # Chuyển đổi MP3 sang WAV
            audio_data = io.BytesIO(response.content)
            audio_segment = AudioSegment.from_mp3(audio_data)
            
            # Tạo temporary file để lưu WAV
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                audio_segment.export(temp_wav.name, format='wav')
                
                # Mở file WAV để phát
                wave_obj = wave.open(temp_wav.name, 'rb')
                
                # Mở stream với thông số từ wave file
                stream = self.p.open(
                    format=self.p.get_format_from_width(wave_obj.getsampwidth()),
                    channels=wave_obj.getnchannels(),
                    rate=wave_obj.getframerate(),
                    output=True
                )
                test1 = self.p.get_format_from_width(wave_obj.getsampwidth())
                test2 = wave_obj.getnchannels()
                test3 = wave_obj.getframerate()
                print(test1)
                print(test2)
                print(test3)
                
                # Đọc và phát audio theo từng chunk
                chunk_size = 1024
                data = wave_obj.readframes(chunk_size)
                while data:
                    stream.write(data)
                    data = wave_obj.readframes(chunk_size)
                
                # Dọn dẹp
                stream.stop_stream()
                stream.close()
                wave_obj.close()
            
        except Exception as e:
            print(f"Lỗi khi sử dụng OpenAI TTS: {e}")

    def __del__(self):
        self.p.terminate() 