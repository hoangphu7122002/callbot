import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pika
import json
import logging
import os
from dotenv import load_dotenv
from freeswitchESL import ESL

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
dotenv_path = os.path.join(ROOT_DIR, ".env")
load_dotenv(dotenv_path)

class QueueHandler:
    def __init__(self):
        
        # RabbitMQ configuration
        self.host = os.getenv('RABBIT_MQ_HOST')
        self.queue_name = os.getenv('RABBIT_MQ_QUEUE')
        
        # ESL configuration for FreeSWITCH
        self.esl_host = os.getenv('ESL_HOST')
        self.esl_port = os.getenv('ESL_PORT')
        self.esl_password = os.getenv('ESL_PASSWORD')
        
        # Ring file for on-hold
        self.ring_file = os.getenv('RINGING_FILE')
        
        # SIP domain
        self.sip_domain = os.getenv('SIP_DOMAIN')
        
        # Connection objects
        self._connection = None
        self._channel = None
        self._esl_con = None
        
    def _get_connection(self):
        """Get or create a RabbitMQ connection."""
        if self._connection is None or self._connection.is_closed:
            self._connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=self.host)
            )
        return self._connection
        
    def _get_channel(self):
        """Get or create a RabbitMQ channel."""
        if self._channel is None or self._channel.is_closed:
            connection = self._get_connection()
            self._channel = connection.channel()
            self._channel.queue_declare(queue=self.queue_name, durable=False)
        return self._channel
        
    def _get_esl_connection(self):
        """Get or create a FreeSWITCH ESL connection."""
        if self._esl_con is None or not self._esl_con.connected():
            print(self.esl_host, self.esl_port, self.esl_password)
            self._esl_con = ESL.ESLconnection(self.esl_host, self.esl_port, self.esl_password)
            if not self._esl_con.connected():
                raise Exception("Failed to connect to FreeSWITCH")
        return self._esl_con
        
    def is_worker_available(self):
        """Check if any worker is available to process calls."""
        try:
            channel = self._get_channel()
            queue = channel.queue_declare(queue=self.queue_name, passive=True)
            return queue.method.message_count > 0 or queue.method.consumer_count > 0
        except Exception as e:
            logging.error(f"Error checking worker availability: {e}")
            return False
            
    def send_to_queue(self, call_data, uuid=None):
        """Send call data to RabbitMQ queue.
        
        If uuid is provided, will play hold music while waiting for a worker.
        """
        try:
            # Check if workers are available
            if self.is_worker_available():
                # Send to queue
                channel = self._get_channel()
                channel.basic_publish(
                    exchange='',
                    routing_key=self.queue_name,
                    body=json.dumps(call_data)
                )
                logging.info(f"Sent call to queue: {call_data['uuid']}")
                return True
            else:
                # No workers available, play hold music if uuid provided
                if uuid:
                    esl_con = self._get_esl_connection()
                    logging.info(f"Playing hold music for {call_data['uuid']}")
                    esl_con.execute("playback", self.ring_file, uuid)
                return False
        except Exception as e:
            logging.error(f"Error sending to queue: {e}")
            return False
            
    def start_consuming(self, callback):
        """Start consuming messages from the queue."""
        try:
            channel = self._get_channel()
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=callback
            )
            
            logging.info("Started consuming messages from queue")
            channel.start_consuming()
        except Exception as e:
            logging.error(f"Error starting consumer: {e}")
            
    def stop_consuming(self):
        """Stop consuming messages from the queue."""
        try:
            if self._channel and self._channel.is_open:
                self._channel.stop_consuming()
                
            if self._connection and self._connection.is_open:
                self._connection.close()
                
            self._channel = None
            self._connection = None
            
            logging.info("Stopped consuming messages from queue")
        except Exception as e:
            logging.error(f"Error stopping consumer: {e}")
            
    def move_call_from_redis_to_queue(self, redis_key, call_data, uuid):
        """Move a call from Redis to RabbitMQ queue."""
        try:
            # Stop the hold music
            esl_con = self._get_esl_connection()
            esl_con.api("uuid_break", uuid)
            
            # Send to queue
            channel = self._get_channel()
            
            # Make sure call_data is a proper JSON string
            if not isinstance(call_data, str):
                import json
                call_data = json.dumps(call_data)
            
            channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=call_data
            )
            
            logging.info(f"Moved call {uuid} from Redis to RabbitMQ")
            return True
        except Exception as e:
            logging.error(f"Error moving call from Redis to queue: {e}")
            return False
            
    def setup_call_listener(self):
        """Set up call listener for FreeSWITCH events."""
        try:
            esl_con = self._get_esl_connection()
            esl_con.events("plain", "CHANNEL_ANSWER CHANNEL_HANGUP")
            logging.info("Set up call listener for FreeSWITCH events")
            return esl_con
        except Exception as e:
            logging.error(f"Error setting up call listener: {e}")
            return None
            
    def close_connections(self):
        """Close all connections."""
        try:
            if self._channel and self._channel.is_open:
                self._channel.close()
                
            if self._connection and self._connection.is_open:
                self._connection.close()
                
            self._channel = None
            self._connection = None
            
            logging.info("Closed RabbitMQ connections")
        except Exception as e:
            logging.error(f"Error closing connections: {e}")
    
    def acknowledge_message(self, channel, delivery_tag):
        """Acknowledge a message from the queue."""
        try:
            channel.basic_ack(delivery_tag=delivery_tag)
            return True
        except Exception as e:
            logging.error(f"Error acknowledging message: {e}")
            return False 