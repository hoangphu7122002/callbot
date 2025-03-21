import pika
import json
from freeswitchESL import ESL
import logging
from minio import Minio
from minio.error import S3Error
import redis
from dotenv import load_dotenv
import os

import os
import sys
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
# dotenv_path = os.path.join(ROOT_DIR, ".env")
# load_dotenv(dotenv_path)

load_dotenv()

# Import metrics for Prometheus monitoring
# from metrics import activate_calls, completed_calls

from prometheus_client import Counter, Gauge, Histogram, Summary
import prometheus_client

# Initialize metrics server
prometheus_client.start_http_server(int(os.getenv("PROMETHEUS_PORT")))  # Metrics will be available on port 18000

# Redis Configuration
redis_client = redis.StrictRedis(host=os.getenv("REDIS_HOST"), port=int(os.getenv("REDIS_PORT")), db=0, decode_responses=True)

# Overall system metrics
activate_calls = Gauge('callbot_active_calls','Number of active calls')
completed_calls = Gauge('callbot_completed_calls','Number of completed calls')
# call_duration = Histogram('callbot_call_duration_seconds','Duration of calls in seconds')

# MinIO server details. Seriously need to redo but lazy rn
minio_client = Minio(
    endpoint=os.getenv('MINIO_HOST'),  
    access_key=os.getenv('MINIO_ACCESS_KEY'),
    secret_key=os.getenv('MINIO_SECRET_KEY'), 
    secure=False
)

# File and bucket details
bucket_name = os.getenv('MINIO_BUCKET_NAME') #Goto Config File
file_path = os.getenv('PRODUCER_RECORD_PATH')  #Goto Config File

def minio_upload(uuid, bucket_name, file_path):
    final_audio_file = file_path + '/' + uuid + '.wav'
    audio_file = uuid+'.wav'
    print(final_audio_file)
    # Check if the bucket exists
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)
        print(f"Bucket '{bucket_name}' created.")
    else:
        print(f"Bucket '{bucket_name}' already exists.")

    # Upload the audio file to MinIO
    try:
        minio_client.fput_object(bucket_name, audio_file, final_audio_file)
        print(f"'{uuid}' has been successfully uploaded to '{bucket_name}'.")
    except S3Error as e:
        print(f"Error uploading file: {e}")

# Thiết lập logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_to_queue(call_data, uuid):
    esl_con = ESL.ESLconnection(os.getenv('ESL_HOST'), os.getenv('ESL_PORT'), os.getenv('ESL_PASSWORD'))
    print("Connect ESL Successfully")
    if not esl_con.connected():
        raise Exception("Failed to connect to FreeSWITCH")
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv('RABBIT_MQ_HOST')))
    channel = connection.channel()
    channel.queue_declare(queue=os.getenv('RABBIT_MQ_QUEUE'), durable=False)

    if is_worker_available(channel):
        channel.basic_publish(exchange='', routing_key=os.getenv('RABBIT_MQ_QUEUE'), body=json.dumps(call_data))
        logging.info(f"Sent to queue: {call_data}")
        connection.close()
        print(f"[Producer] Sent Call to RabbitMQ")
    else:
        redis_client.set(f"calldata:{call_data}", json.dumps(call_data)) #No TTL
        print(f"[Producer] Stored calldata in Redis as no worker is available")
        print("Playing Playback")
        queue_file = os.getenv('RINGING_FILE')
        esl_con.execute("playback", queue_file, uuid)
        #esl_con.execute("start_hold_music", queue_file, uuid)
        connection.close()

# Check if any worker is available
def is_worker_available(rabbitmq_channel):
    queue = rabbitmq_channel.queue_declare(queue=os.getenv('RABBIT_MQ_QUEUE'), passive=True)
    return queue.method.message_count > 0 or queue.method.consumer_count > 0

class CallListener:
    def __init__(self):
        self.esl_con = ESL.ESLconnection(os.getenv('ESL_HOST'), os.getenv('ESL_PORT'), os.getenv('ESL_PASSWORD'))
        if not self.esl_con.connected():
            raise Exception("Failed to connect to FreeSWITCH")

    def listen_for_calls(self):
        self.esl_con.events("plain", "CHANNEL_ANSWER CHANNEL_HANGUP")
        logging.info("Listening for calls...")

        while True:
            e = self.esl_con.recvEvent()
            if e:
                event_name = e.getHeader("Event-Name")
                
                if event_name == "CHANNEL_ANSWER":
                    uuid = e.getHeader("Unique-ID")
                    sip_from = e.getHeader("variable_sip_from_user")
                    media_port = e.getHeader("variable_local_media_port")
                    sip_domain = e.getHeader("variable_sip_to_host")
                    sip_to = e.getHeader("variable_sip_to_user")

                    if sip_to == "media" and sip_domain == os.getenv('SIP_DOMAIN'):
                        call_data = {
                            "uuid": uuid,
                            "sip_from": sip_from,
                            "media_port": media_port
                        }
                        
                        # Increment active calls counter when a new call starts
                        activate_calls.inc()
                        
                        send_to_queue(call_data, uuid)
                        logging.info(f"New call from {sip_from}, UUID: {uuid}")
                
                elif event_name == "CHANNEL_HANGUP":
                    uuid = e.getHeader("Unique-ID")
                    sip_to = e.getHeader("variable_sip_to_user")
                    # sip_from = e.getHeader("variable_sip_from_user")
                    sip_domain = e.getHeader("variable_sip_to_host")
                    if sip_to == "media" and sip_domain == os.getenv('SIP_DOMAIN'):
                        logging.info(f"Call ended: UUID {uuid}")
                        # Decrement active calls counter and increment completed calls counter when a call ends
                        activate_calls.dec()
                        completed_calls.inc()
                        minio_upload(uuid, bucket_name, file_path)

if __name__ == "__main__":
    listener = CallListener()
    listener.listen_for_calls()
