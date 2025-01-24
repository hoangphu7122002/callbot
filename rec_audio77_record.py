import socket
import wave
import struct
from freeswitchESL import ESL
import threading
import os
import time

record_file_path = "/home/hm1905/records"

# Biến toàn cục để kiểm soát trạng thái cuộc gọi
is_running = True  # Trạng thái cuộc gọi


def decode_pcmu_to_pcm16(pcmu_data):
    """ Giải mã dữ liệu PCMU sang PCM 16-bit."""
    decoded_pcm = bytearray()
    for byte in pcmu_data:
        ulaw_byte = ~byte & 0xFF
        sign = (ulaw_byte & 0x80) >> 7
        exponent = (ulaw_byte & 0x70) >> 4
        mantissa = ulaw_byte & 0x0F
        linear_value = ((0x21 << exponent) + (mantissa << (exponent + 3))) - 0x84
        if sign == 0:
            linear_value = -linear_value
        decoded_pcm.extend(struct.pack('>h', linear_value))
    return bytes(decoded_pcm)


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
            try:
                data, addr = sock.recvfrom(2048)
                if not data:
                    break
                
                # Tách phần payload RTP
                rtp_payload = data[12:]  # Bỏ header RTP (12 bytes)
                # Giải mã payload RTP từ PCMU sang PCM 16-bit
                pcm_data = decode_pcmu_to_pcm16(rtp_payload)

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

                if sip_to == "media" and sip_domain == "34.29.227.22":
                    print(f"New call detected with UUID: {uuid}, SIP To: {sip_to}@{sip_domain}")

                    output_dir = f"{record_file_path}/{uuid}"
                    os.makedirs(output_dir, exist_ok=True)
                    active_calls[uuid] = {
                        "batch_count": 0,
                        "output_dir": output_dir,
                        "file_parts": []
                    }

                    # Start batch recording every 3 seconds in a loop
                    def batch_record():
                        while uuid in active_calls:
                            batch_file = f"{output_dir}/part_{active_calls[uuid]['batch_count']:03d}.wav"
                            active_calls[uuid]["file_parts"].append(batch_file)

                            record_command = f"uuid_record {uuid} start {batch_file}"
                            con.api(record_command)
                            print(f"Recording batch {active_calls[uuid]['batch_count']} for UUID: {uuid}")

                            time.sleep(3)

                            stop_command = f"uuid_record {uuid} stop"
                            con.api(stop_command)
                            print(f"Stopped recording batch {active_calls[uuid]['batch_count']} for UUID: {uuid}")

                            active_calls[uuid]['batch_count'] += 1

                    threading.Thread(target=batch_record, daemon=True).start()

                else:
                    print(f"Ignoring call with SIP To: {sip_to}@{sip_domain}")

            elif event_name == "CHANNEL_HANGUP":
                uuid = e.getHeader("Unique-ID")

                if uuid in active_calls:
                    print(f"Call with UUID: {uuid} has ended.")

                    # Stop active batch recording
                    del active_calls[uuid]  # Removing UUID stops the batch recording thread


    if con:
        con.disconnect()


if __name__ == "__main__":
    try:
        listen_for_calls()
    except KeyboardInterrupt:
        print("Shutting down...")
