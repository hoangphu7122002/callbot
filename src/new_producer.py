#!/usr/bin/env python3
import json
import logging
import os
from dotenv import load_dotenv
from src.db_handler import DBHandler
from src.queue_handler import QueueHandler
import prometheus_client
from prometheus_client import Counter, Gauge, Histogram, Summary
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.getenv('LOGGING_FILE', 'callbot.log')),
        logging.StreamHandler()
    ]
)

# Initialize Prometheus metrics
prometheus_client.start_http_server(int(os.getenv("PROMETHEUS_PORT", "18000")))
activate_calls = Gauge('callbot_active_calls', 'Number of active calls')
completed_calls = Gauge('callbot_completed_calls', 'Number of completed calls')

# Initialize handlers - producer needs Redis (for storing calls) and MinIO (for uploading recordings)
db_handler = DBHandler(init_postgres=False, init_redis=True, init_minio=True)
queue_handler = QueueHandler()

class CallListener:
    """Listens for call events from FreeSWITCH and processes them."""
    
    def __init__(self):
        """Initialize the call listener."""
        self.esl_con = queue_handler.setup_call_listener()
        if not self.esl_con:
            raise Exception("Failed to connect to FreeSWITCH")
            
    def listen_for_calls(self):
        """Listen for call events and process them."""
        logging.info("Listening for calls...")
        
        while True:
            e = self.esl_con.recvEvent()
            if e:
                event_name = e.getHeader("Event-Name")
                
                if event_name == "CHANNEL_ANSWER":
                    self._handle_call_answer(e)
                elif event_name == "CHANNEL_HANGUP":
                    self._handle_call_hangup(e)
    
    def _handle_call_answer(self, event):
        """Handle a call answer event."""
        uuid = event.getHeader("Unique-ID")
        sip_from = event.getHeader("variable_sip_from_user")
        media_port = event.getHeader("variable_local_media_port")
        sip_domain = event.getHeader("variable_sip_to_host")
        sip_to = event.getHeader("variable_sip_to_user")
        
        # Check if this is a call to our media endpoint
        if sip_to == "media" and sip_domain == os.getenv('SIP_DOMAIN'):
            call_data = {
                "uuid": uuid,
                "sip_from": sip_from,
                "media_port": media_port
            }
            
            # Increment active calls counter
            activate_calls.inc()
            
            # Send call to queue or store in Redis if no workers available
            if queue_handler.send_to_queue(call_data, uuid):
                logging.info(f"New call from {sip_from}, UUID: {uuid} - sent to queue")
            else:
                # Store in Redis if no workers available
                db_handler.store_call_data(call_data)
                logging.info(f"New call from {sip_from}, UUID: {uuid} - stored in Redis (no workers available)")
    
    def _handle_call_hangup(self, event):
        """Handle a call hangup event."""
        uuid = event.getHeader("Unique-ID")
        sip_to = event.getHeader("variable_sip_to_user")
        sip_domain = event.getHeader("variable_sip_to_host")
        
        if sip_to == "media" and sip_domain == os.getenv('SIP_DOMAIN'):
            # Decrement active calls and increment completed calls
            activate_calls.dec()
            completed_calls.inc()
            
            # Upload recording to MinIO - simple approach like original
            if db_handler.upload_audio_to_minio(uuid):
                logging.info(f"Call ended: UUID {uuid} - recording uploaded to MinIO")
            else:
                logging.error(f"Call ended: UUID {uuid} - failed to upload recording to MinIO")

def main():
    """Main function to start the call listener."""
    try:
        listener = CallListener()
        listener.listen_for_calls()
    except KeyboardInterrupt:
        logging.info("Producer stopped by user")
    except Exception as e:
        logging.error(f"Error in producer: {e}")
    finally:
        # Close connections
        queue_handler.close_connections()

if __name__ == "__main__":
    main() 