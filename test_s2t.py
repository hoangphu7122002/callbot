
import openai

# Cấu hình API key của OpenAI
openai.api_key = "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"  # Thay bằng API key của bạn

def speech_to_text_from_wav(file_path):
    """
    Chuyển đổi âm thanh từ file WAV sang văn bản bằng OpenAI Whisper.
    """
    try:
        with open(file_path, "rb") as audio_file:
            print("Đang gửi file âm thanh để xử lý...")
            #response = openai.Audio.transcribe("whisper-1", audio_file)
            response = openai.Audio.transcribe("whisper-1", audio_file, language="vi")
            return response.get("text", "")
    except Exception as e:
        print(f"Lỗi khi chuyển đổi file âm thanh: {e}")
        return None

if __name__ == "__main__":
    # Đường dẫn tới file WAV cần chuyển đổi
    wav_file_path =  "/home/hm1905/records/1f5f4e76-f45c-4fd9-9c92-63bf93d60f1a.wav"  # Thay bằng đường dẫn file WAV

    # Gọi hàm chuyển đổi
    transcript = speech_to_text_from_wav(wav_file_path)

    # Hiển thị kết quả
    if transcript:
        print("Văn bản chuyển đổi:")
        print(transcript)
    else:
        print("Không thể chuyển đổi file âm thanh.")
