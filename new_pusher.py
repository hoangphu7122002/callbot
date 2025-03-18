#!/usr/bin/env python3
import json
import time
import logging
import os
from threading import Thread
from dotenv import load_dotenv
from src.db_handler import DBHandler
from src.queue_handler import QueueHandler

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

# Initialize handlers - pusher only needs Redis for call data storage/retrieval
db_handler = DBHandler(init_postgres=False, init_redis=True, init_minio=False)
queue_handler = QueueHandler()

def handle_hangup_event():
    """Monitor FreeSWITCH events for hangups and remove associated Redis entries."""
    # Set up ESL connection for hangup monitoring
    esl_con = queue_handler._get_esl_connection()
    esl_con.events("plain", "CHANNEL_HANGUP")
    
    logging.info("Hangup monitor started")
    
    while True:
        e = esl_con.recvEventTimed(1)  # 1 second timeout
        if e:
            event_name = e.getHeader("Event-Name")
            if event_name == "CHANNEL_HANGUP":
                call_id = e.getHeader("Unique-ID")
                if call_id:
                    # Find the Redis key for this call ID
                    key = f"calldata:{call_id}"
                    call_data = db_handler.get_call_data(key)
                    
                    if call_data:
                        db_handler.remove_call_data(key)
                        logging.info(f"Removed message {key} from Redis due to hangup event")

def push_calls_to_queue():
    """Monitor RabbitMQ and move calls from Redis when workers become available."""
    logging.info("Queue pusher started")
    
    while True:
        try:
            # Check if there are workers available and no messages in the queue
            channel = queue_handler._get_channel()
            queue_info = channel.queue_declare(queue=queue_handler.queue_name, passive=True)
            
            if queue_info.method.message_count == 0 and queue_info.method.consumer_count > 0:
                # Get the oldest call from Redis
                last_id, call_data, uuid = db_handler.get_last_stored_call_data()
                
                if call_data and uuid:
                    # Try to ensure call_data is properly formatted
                    if isinstance(call_data, str):
                        try:
                            # Make sure it's valid JSON
                            import json
                            json.loads(call_data)
                        except json.JSONDecodeError:
                            # If it's not valid JSON, try to convert Python string representation to JSON
                            if call_data.startswith("{'uuid'"):
                                call_data = call_data.replace("'", '"')
                                logging.warning(f"Converted malformed data to JSON for {uuid}")
                    
                    # Stop any hold music that might be playing
                    esl_con = queue_handler._get_esl_connection()
                    esl_con.api("uuid_break", uuid)
                    
                    # Move the call to the queue
                    if queue_handler.move_call_from_redis_to_queue(last_id, call_data, uuid):
                        # Remove from Redis on success
                        db_handler.remove_call_data(last_id)
                        logging.info(f"Moved call {uuid} from Redis to queue")
            
            # Sleep briefly to prevent hammering the systems
            time.sleep(0.5)
            
        except Exception as e:
            logging.error(f"Error in push_calls_to_queue: {e}")
            time.sleep(1)  # Sleep longer on error

def main():
    """Main function to start the pusher threads."""
    try:
        # Start hangup monitor thread
        hangup_thread = Thread(target=handle_hangup_event)
        hangup_thread.daemon = True
        hangup_thread.start()
        
        # Start queue pusher thread
        pusher_thread = Thread(target=push_calls_to_queue)
        pusher_thread.daemon = True
        pusher_thread.start()
        
        # Keep the main thread alive
        logging.info("Pusher service started")
        while True:
            time.sleep(10)
            
    except KeyboardInterrupt:
        logging.info("Pusher stopped by user")
    except Exception as e:
        logging.error(f"Error in pusher: {e}")
    finally:
        # Close connections
        queue_handler.close_connections()

if __name__ == "__main__":
    main() 