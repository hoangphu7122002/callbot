import pyaudio
import wave
import numpy as np
import io

class AudioHandler:
    def __init__(self, chunk=1024, channels=1, rate=24000, 
                 silence_threshold=300, silence_chunks=100, 
                 initial_silence_chunks=80):
        # Original attributes
        self.chunk = chunk
        self.channels = channels
        self.rate = rate
        self.silence_threshold = silence_threshold
        self.silence_chunks = silence_chunks
        self.initial_silence_chunks = initial_silence_chunks
        
        # Alternative uppercase format (optional)
        # self.CHUNK = chunk
        # self.FORMAT = pyaudio.paInt16
        # self.CHANNELS = channels
        # self.RATE = rate
        # self.SILENCE_THRESHOLD = silence_threshold
        # self.SILENCE_CHUNKS = silence_chunks
        # self.INITIAL_SILENCE_CHUNKS = initial_silence_chunks
        
        self.p = pyaudio.PyAudio()
        
        # Add device selection support
        self.list_audio_devices()
        self.input_device_index = self.get_default_input_device()

    def list_audio_devices(self):
        """Liệt kê tất cả các audio devices"""
        print("\nCác thiết bị âm thanh khả dụng:")
        for i in range(self.p.get_device_count()):
            dev = self.p.get_device_info_by_index(i)
            if dev.get('maxInputChannels') > 0:  # Chỉ hiện thị input devices
                print(f"Index {i}: {dev.get('name')}")
        print()

    def get_default_input_device(self):
        """Lấy default input device hoặc device đầu tiên có sẵn"""
        try:
            default_index = self.p.get_default_input_device_info().get('index')
            return default_index
        except:
            # Nếu không lấy được default device, tìm device đầu tiên có input channels
            for i in range(self.p.get_device_count()):
                dev = self.p.get_device_info_by_index(i)
                if dev.get('maxInputChannels') > 0:
                    return i
            return None

    def record_audio(self):
        """Record audio from microphone"""
        stream = self.p.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            input_device_index=self.input_device_index,
            frames_per_buffer=self.CHUNK
        )

        print("* Đang lắng nghe...")

        frames = []
        silent_chunks = 0
        initial_silent_chunks = 0
        has_speech = False

        while True:
            data = stream.read(self.CHUNK, exception_on_overflow=False)
            frames.append(data)
            
            # Convert audio chunks to array for amplitude checking
            audio_data = np.frombuffer(data, dtype=np.int16)
            amplitude = np.max(np.abs(audio_data))

            if amplitude > self.SILENCE_THRESHOLD:
                has_speech = True
                silent_chunks = 0
            else:
                silent_chunks += 1
                if not has_speech:
                    initial_silent_chunks += 1

            # Dừng nếu im lặng quá lâu sau khi đã phát hiện tiếng nói
            if has_speech and silent_chunks > self.SILENCE_CHUNKS:
                print(f"Dừng ghi âm: {silent_chunks} chunk im lặng sau tiếng nói")
                break

            # Dừng nếu im lặng quá lâu ngay từ đầu
            if not has_speech and initial_silent_chunks > self.INITIAL_SILENCE_CHUNKS:
                print("Không phát hiện tiếng nói")
                stream.stop_stream()
                stream.close()
                return None

        stream.stop_stream()
        stream.close()

        if not has_speech:
            return None

        # Convert frames to WAV format
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(frames))

        return wav_buffer.getvalue()

    def play_audio(self, audio_data):
        """Play audio from bytes data"""
        # Convert bytes to wave file in memory
        wav_buffer = io.BytesIO(audio_data)
        with wave.open(wav_buffer, 'rb') as wf:
            # Open stream
            stream = self.p.open(
                format=self.p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )

            # Read data
            data = wf.readframes(self.CHUNK)

            # Play stream
            while data:
                stream.write(data)
                data = wf.readframes(self.CHUNK)

            # Cleanup
            stream.stop_stream()
            stream.close()

    def __del__(self):
        """Cleanup PyAudio"""
        self.p.terminate() 