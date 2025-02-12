# import ESL
from freeswitchESL import ESL
import asyncio
from rtp_bot import RTPBot  # Callbot của bạn
import threading

def forward_rtp(uuid,rtp_port ,rtp_host="127.0.0.1"):
    """ 
    Cấu hình FreeSWITCH để chuyển RTP đến địa chỉ rtp_host:rtp_port.
    """
    con = ESL.ESLconnection("127.0.0.1", "8021", "ClueCon")  # Kết nối với FreeSWITCH qua ESL
    if con.connected():
        print(f"Connected to FreeSWITCH for call: {uuid}")

        # Thiết lập địa chỉ RTP đích qua biến tùy chỉnh
        set_rtp_host = f"uuid_dump {uuid}"
        #set_rtp_port = f"uuid_setvar {uuid} rtp_port {rtp_port}"

        # Thêm media bug để forward RTP
        #add_media_bug = f"uuid_setvar {uuid} variable_rtp_sendonly rtp {rtp_host}:{rtp_port}"
        # Gửi các lệnh ESL
        print("============")
        host_response = con.api(set_rtp_host)
        print("============")
        #port_response = con.api(set_rtp_port)
        #bug_response = con.api(add_media_bug)

        #print(f"RTP Host Set Response: {host_response.getBody()}")
        #print(f"RTP Port Set Response: {port_response.getBody()}")
        #print(f"Media Bug Response: {bug_response.getBody()}")
        rtp_forward_command = f"uuid_setvar {uuid} media_bug_app rtp_forward"
        rtp_forward_target = f"uuid_setvar {uuid} rtp_forward_target 127.0.0.1:5006"
        
        # Apply settings
        con.api(rtp_forward_command)
        con.api(rtp_forward_target)
        print(f"RTP forwarding set to 127.0.0.1:5006 for UUID: {uuid}")
    else:
        print("Failed to connect to FreeSWITCH.")


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

                # Lọc cuộc gọi đến SIP To: media@34.29.227.22:5080
                if sip_to == "media" and sip_domain == "34.29.227.22":
                    print(e.serialize())
                    variable_local_media_port = e.getHeader("variable_local_media_port")
                    print(f"New call detected with UUID: {uuid}, SIP To: {sip_to}@{sip_domain}")
                    # Chuyển RTP đến Callbot
                    print('media port:',variable_local_media_port)
                    forward_rtp(uuid,'')
                    start_bot(uuid, int(variable_local_media_port))
                else:
                    print(f"Ignoring call with SIP To: {sip_to}@{sip_domain}")

def start_bot(uuid, rtp_port):
    """
    Khởi động Callbot và lắng nghe RTP.
    """
    bot = RTPBot(local_ip = "127.0.0.1",local_port = rtp_port,remote_ip = "127.0.0.1",remote_port = "5006",uuid = uuid)
    bot_thread = threading.Thread(target=bot.start)
    bot_thread.start()

if __name__ == "__main__":
    try:
        # Khởi động Callbot
        #start_bot()

        # Lắng nghe sự kiện từ FreeSWITCH
        listen_for_calls()
    except KeyboardInterrupt:
        print("Shutting down...")
