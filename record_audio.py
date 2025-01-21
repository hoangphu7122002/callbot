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

def forward_rtp(uuid, rtp_port = "5006", rtp_host="10.128.0.7"):
    """ Cấu hình FreeSWITCH để chuyển RTP đến địa chỉ rtp_host:rtp_port"""
    con = ESL.ESLconnection("127.0.0.1", "8021", "ClueCon")
    if con.connected():
        print(f"Connected to FreeSWITCH for call: {uuid}")

        # Cấu hình RTP forwarding
        con.api(f"uuid_setvar {uuid} media_bug_app rtp_forward")
        con.api(f"uuid_setvar {uuid} rtp_forward_target {rtp_host}:{rtp_port}")
        print(f"RTP forwarding set to {rtp_host}:{rtp_port} for UUID: {uuid}")
    else:
        print("Failed to connect to FreeSWITCH.")

def listen_rtp(port, output_file):
    """
    Lắng nghe RTP trên một cổng cụ thể và ghi âm vào file WAV.
    """
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
        while True:
            # Nhận dữ liệu từ socket
            data, addr = sock.recvfrom(2048)
            print(data)
            # Giải mã payload RTP (giả sử codec G711, bỏ 12 byte header RTP)
            rtp_payload = data[12:]

            # Ghi dữ liệu vào file WAV
            wf.writeframes(rtp_payload)
    except KeyboardInterrupt:
        print("Stopping RTP listener.")
    finally:
        wf.close()
        sock.close()

def listen_for_calls():
    """
    Lắng nghe sự kiện CHANNEL_CREATE từ FreeSWITCH.
    """
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
                    forward_rtp(uuid, int(media_port))

                    # Lắng nghe và ghi RTP
                    output_file = f"{record_file_path}/{uuid}.wav"
                    #con.api("uuid_record", f"{uuid} start {output_file}")
                    #print(f"Recording started: {record_file_path}")
                    threading.Thread(target=listen_rtp, args=(int(media_port), output_file)).start()
                else:
                    print(f"Ignoring call with SIP To: {sip_to}@{sip_domain}")

if __name__ == "__main__":
    try:
        listen_for_calls()
    except KeyboardInterrupt:
        print("Shutting down...")
