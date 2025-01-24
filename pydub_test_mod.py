import socket
import wave
import struct
from freeswitchESL import ESL
import threading
from pydub import AudioSegment  # Sử dụng pydub để xử lý âm thanh
from pydub.utils import which
import audioop

AudioSegment.converter = which("ffmpeg")
record_file_path = "/home/hm1905/records"

# Biến toàn cục để kiểm soát trạng thái cuộc gọi
is_running = True  # Trạng thái cuộc gọi


def decode_pcmu_to_pcm16(pcmu_data):
    """Giải mã dữ liệu PCMU (G.711u) sang PCM 16-bit."""
    pcm_data = audioop.alaw2lin(pcmu_data, 2)
    #decoded = AudioSegment(data=pcmu_data, sample_width=1, frame_rate=8000, channels=1, codec="ulaw")
    #return decoded.raw_data
    return pcm_data

from pydub import AudioSegment
import io

def _decode_pcmu_to_pcm16(pcmu_data):
    """
    Giải mã dữ liệu PCMU (G.711u) sang PCM 16-bit bằng pydub.
    """
    try:
        # Chuyển đổi dữ liệu PCMU thành một đối tượng BytesIO
        pcmu_stream = io.BytesIO(pcmu_data)

        # Tạo AudioSegment từ BytesIO với codec ulaw
        decoded_segment = AudioSegment.from_file(pcmu_stream, format="raw", codec="ulaw", frame_rate=8000, channels=1, sample_width=2)

        # Trả về dữ liệu đã giải mã dưới dạng PCM 16-bit
        return decoded_segment.raw_data
    except Exception as e:
        print(f"Error decoding PCMU data: {e}")
        return b""




def listen_rtp(port, output_file):

    """
    Lắng nghe RTP trên một cổng cụ thể và ghi âm vào file WAV.
    """
    global is_running

    # Tạo socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("10.128.0.7", port))
    print(f"Listening for RTP packets on 10.128.0.7:{port}")

    # Cấu hình file WAV
    wf = wave.open(output_file, 'wb')
    wf.setnchannels(1)  # Mono
    wf.setsampwidth(2)  # 16-bit
    wf.setframerate(8000)  # G711 thường là 8000 Hz

    try:
        while is_running:
            #try:
                data, addr = sock.recvfrom(1024)
                if not data:
                    break
                
                # Tách phần payload RTP
                rtp_payload = data[12:]  # Bỏ header RTP (12 bytes)
                
                # Giải mã payload RTP từ PCMU sang PCM 16-bit
                pcm_data = decode_pcmu_to_pcm16(rtp_payload)

                # Ghi dữ liệu PCM vào file WAV
                wf.writeframes(pcm_data)
            #except Exception as e:
            #    if is_running:
            #        print(f"Lỗi khi nhận RTP: {e}")
    except KeyboardInterrupt:
        print("Stopping RTP listener.")
    finally:
        wf.close()
        sock.close()


def listen_for_calls():
    """
    Lắng nghe sự kiện CHANNEL_CREATE từ FreeSWITCH.
    """
    global is_running

    # Dictionary to track active calls
    active_calls = {}

    con = ESL.ESLconnection("127.0.0.1", "8021", "ClueCon")
    if not con.connected():
        print("Failed to connect to FreeSWITCH.")
        return

    # Subscribe to CHANNEL_ANSWER and CHANNEL_HANGUP events
    con.events("plain", "CHANNEL_ANSWER CHANNEL_HANGUP")
    print("Listening for CHANNEL_ANSWER and CHANNEL_HANGUP events...")

    while True:
        e = con.recvEvent()
        if e:
            event_name = e.getHeader("Event-Name")

            if event_name == "CHANNEL_ANSWER":
                uuid = e.getHeader("Unique-ID")
                sip_to = e.getHeader("variable_sip_to_user")
                sip_domain = e.getHeader("variable_sip_to_host")
                media_port = e.getHeader("variable_local_media_port")

                if sip_to == "media" and sip_domain == "34.29.227.22":
                    print(f"New call detected with UUID: {uuid}, SIP To: {sip_to}@{sip_domain}")

                    output_file = f"{record_file_path}/{uuid}.wav"
                    active_calls[uuid] = {
                        "thread": threading.Thread(target=listen_rtp, args=(int(media_port), output_file)),
                        "port": media_port
                    }
                    
                    active_calls[uuid]["thread"].start()
                    is_running = True
                else:
                    print(f"Ignoring call with SIP To: {sip_to}@{sip_domain}")

            elif event_name == "CHANNEL_HANGUP":
                uuid = e.getHeader("Unique-ID")

                if uuid in active_calls:
                    print(f"Call with UUID: {uuid} has ended.")
                    
                    # Stop the thread or processing associated with the call
                    active_calls[uuid]["thread"].join()  # Ensure thread is stopped
                    del active_calls[uuid]  # Remove from active_calls

    if con:
        con.disconnect()


if __name__ == "__main__":
    try:
        listen_for_calls()
    except KeyboardInterrupt:
        print("Shutting down...")
