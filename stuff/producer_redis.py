import pika
import json
from freeswitchESL import ESL
import logging
from minio import Minio
from minio.error import S3Error
import redis


# MinIO server details. Seriously need to redo but lazy rn
minio_client = Minio(
    endpoint='34.174.214.130:19000',  
    access_key='IxcPVSr0nlkyE96Xe0MW',
    secret_key='dzwBMkEw9hxYSiUBh5It1sRiG44YnkgKmDb3DH5L', 
    secure=False
)

# Redis Configuration
redis_client = redis.StrictRedis(host='localhost', port=6380, db=0, decode_responses=True)

# File and bucket details
bucket_name = 'call-record' #Goto Config File
file_path = '/home/hm1905/records/'  #Goto Config File

def minio_upload(uuid, bucket_name, file_path):
    final_audio_file = file_path + uuid + '.wav'
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

def send_to_queue(call_data):
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='call_queue', durable=True)

    if is_worker_available(channel):
        channel.basic_publish(exchange='', routing_key='call_queue', body=json.dumps(call_data))
        logging.info(f"Sent to queue: {call_data}")
        connection.close()
        print(f"[Producer] Sent Call to RabbitMQ")
    else:
        redis_client.set(f"calldata:{call_data}", json.dumps(call_data)) #No TTL
        print(f"[Producer] Stored calldata in Redis as no worker is available")


# Check if any worker is available
def is_worker_available(rabbitmq_channel):
    queue = rabbitmq_channel.queue_declare(queue='call_queue', passive=True)
    return queue.method.message_count > 0 or queue.method.consumer_count > 0

class CallListener:
    def __init__(self):
        self.esl_con = ESL.ESLconnection("127.0.0.1", "8021", "ClueCon")
        if not self.esl_con.connected():
            raise Exception("Failed to connect to FreeSWITCH")

    def listen_for_calls(self):
        self.esl_con.events("plain", "CHANNEL_ANSWER CHANNEL_HANGUP")
        logging.info("Listening for calls...")

        while True:
            # e = self.esl_con.recvEvent()
            e = self.esl_con.recvEventTimed(1)
            if e:
                event_name = e.getHeader("Event-Name")
                
                if event_name == "CHANNEL_ANSWER":
                    uuid = e.getHeader("Unique-ID")
                    sip_from = e.getHeader("variable_sip_from_user")
                    media_port = e.getHeader("variable_local_media_port")
                    sip_domain = e.getHeader("variable_sip_to_host")
                    sip_to = e.getHeader("variable_sip_to_user")

                    if sip_to == "media" and sip_domain == "34.174.214.130":
                        call_data = {
                            "uuid": uuid,
                            "sip_from": sip_from,
                            "media_port": media_port
                        }
                        
                        send_to_queue(call_data)
                        logging.info(f"New call from {sip_from}, UUID: {uuid}")
                
                elif event_name == "CHANNEL_HANGUP":
                    uuid = e.getHeader("Unique-ID")
                    logging.info(f"Call ended: UUID {uuid}")
                    sip_to = e.getHeader("variable_sip_to_user")
                    # sip_from = e.getHeader("variable_sip_from_user")
                    sip_domain = e.getHeader("variable_sip_to_host")
                    # if sip_to == "media" and sip_domain == "34.174.214.130":
                    #     minio_upload(uuid, bucket_name, file_path)

if __name__ == "__main__":
    listener = CallListener()
    listener.listen_for_calls()
