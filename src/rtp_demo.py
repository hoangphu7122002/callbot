import time
from rtp_handler import RTPHandler

def main():
    # Khởi tạo hai instance của RTPHandler cho hai endpoint
    endpoint1 = RTPHandler(
        local_ip="127.0.0.1",
        local_port=12345,
        remote_ip="127.0.0.1",
        remote_port=12346
    )
    
    endpoint2 = RTPHandler(
        local_ip="127.0.0.1",
        local_port=12346,
        remote_ip="127.0.0.1",
        remote_port=12345
    )
    
    try:
        # Bắt đầu ghi âm và phát cho cả hai endpoint
        print("Bắt đầu demo RTP stream...")
        endpoint1.start_recording()
        endpoint1.start_playing()
        
        endpoint2.start_recording()
        endpoint2.start_playing()
        
        # Chạy trong 30 giây
        time.sleep(30)
        
    except KeyboardInterrupt:
        print("\nDừng demo...")
    finally:
        # Dọn dẹp
        endpoint1.stop()
        endpoint2.stop()
        print("Demo kết thúc")

if __name__ == "__main__":
    main() 