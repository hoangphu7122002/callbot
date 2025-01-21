import socket
import wave
import socket
import wave
import struct

from freeswitchESL import ESL
import asyncio
#from rtp_bot import RTPBot  # Callbot của bạn
import threading
import socket
import wave


record_file_path = "/home/hm1905/records"

# Biến toàn cục để kiểm soát trạng thái cuộc gọi
is_running = True  # Trạng thái cuộc gọi

def decode_pcmu_to_pcm16(pcmu_data):
    """
    Giải mã dữ liệu PCMU sang PCM 16-bit.
    """
    decoded_pcm = bytearray()
    for byte in pcmu_data:
        pcm_value = byte - 128  # Chuyển giá trị từ G.711 (0-255) về âm thanh (-32768 đến 32767)
        pcm_value *= 256  # Tăng độ phân giải thành 16-bit
        decoded_pcm.extend(pcm_value.to_bytes(2, byteorder='little', signed=True))
    return bytes(decoded_pcm)

def listen_rtp(port, output_file):
    """
    Lắng nghe RTP trên một cổng cụ thể và ghi âm vào file WAV.
    """
    global is_running  # Biến toàn cục cần được khai báo

    # Tạo socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Cho phép tái sử dụng cổng
    sock.bind(("10.128.0.7", port))
    print(f"Listening for RTP packets on 10.128.0.7:{port}")

    # Cấu hình file WAV
    wf = wave.open(output_file, 'wb')
    wf.setnchannels(1)  # Mono
    wf.setsampwidth(2)  # 16-bit
    wf.setframerate(8000)  # G711 thường là 8000 Hz

    try:
        while is_running:  # Dùng biến toàn cục is_running
            try:
                data, addr = sock.recvfrom(2048)
                if not data:
                    break  # Thoát khi nhận không có dữ liệu
                
                # Tách phần payload RTP
                rtp_payload = data[12:]  # Bỏ header RTP (12 bytes)
                # Giải mã payload RTP từ PCMU sang PCM 16-bit
                pcm_data = decode_pcmu_to_pcm16(rtp_payload)
                print(pcm_data)

                # Ghi dữ liệu PCM vào file WAV
                wf.writeframes(pcm_data)
            except Exception as e:
                if is_running:
                    print(f"Lỗi khi nhận RTP: {e}")
       
    except KeyboardInterrupt:
        print("Stopping RTP listener.")
    finally:
        wf.close()
        sock.close()

def listen_for_calls():
    """
    Lắng nghe sự kiện CHANNEL_CREATE từ FreeSWITCH.
    """
    global is_running  # Biến toàn cục cần được khai báo

    # Kết nối tới FreeSWITCH (ESL)
    con = ESL.ESLconnection("127.0.0.1", "8021", "ClueCon")
    if not con.connected():
        print("Failed to connect to FreeSWITCH.")
        return

    # Subscribe to CHANNEL_CREATE events
    con.events("plain", "CHANNEL_ANSWER")
    print("Listening for CHANNEL_ANSWER events...")

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

                    # Chuyển RTP đến Callbot
                    # forward_rtp(uuid, int(media_port))

                    # Lắng nghe và ghi RTP
                    output_file = f"{record_file_path}/{uuid}.wav"
                    threading.Thread(target=listen_rtp, args=(int(media_port), output_file)).start()

                    # Set global is_running to True when listening
                    is_running = True
                    try:
                        while is_running:
                            e = con.recvEvent()
                            if e and e.getHeader("Event-Name") == "CHANNEL_HANGUP":
                                print("Call ended, stopping listener.")
                                is_running = False  # Dừng vòng lặp khi cuộc gọi kết thúc
                            
                    except KeyboardInterrupt:
                        print("Shutting down...")
                        is_running = False
                else:
                    print(f"Ignoring call with SIP To: {sip_to}@{sip_domain}")

    if con:
        con.disconnect()

if __name__ == "__main__":
    try:
        listen_for_calls()
    except KeyboardInterrupt:
        print("Shutting down...")
