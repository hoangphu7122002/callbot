import pika
import redis
import json
import time
from threading import Thread
from freeswitchESL import ESL
import asyncio
import os
from dotenv import load_dotenv

import os
import sys
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
# dotenv_path = os.path.join(ROOT_DIR, ".env")
# load_dotenv(dotenv_path)

load_dotenv()
# Redis Configuration
redis_client = redis.StrictRedis(host=os.getenv('REDIS_HOST'), port=int(os.getenv('REDIS_PORT')), db=0, decode_responses=True)

# RabbitMQ Configuration
rabbitmq_connection = pika.BlockingConnection(pika.ConnectionParameters(os.getenv('RABBIT_MQ_HOST')))
rabbitmq_channel = rabbitmq_connection.channel()
rabbitmq_channel.queue_declare(queue=os.getenv('RABBIT_MQ_QUEUE'), durable=False)



def get_last_stored_calldata():
    keys = redis_client.keys("calldata:*")
    if keys:
        last_id = sorted(keys)[-1]  # Get the last stored message
        call_data = redis_client.get(last_id)

        uuid = json.loads(call_data).get("uuid")
        return last_id, call_data, uuid
    return None, None, None

def handle_hangup_event():
    #ESL Configuration
    esl_con = ESL.ESLconnection(os.getenv('ESL_HOST'), os.getenv('ESL_PORT'), os.getenv('ESL_PASSWORD'))
    #print("Connect ESL Successfully")
    if not esl_con.connected():
        raise Exception("Failed to connect to FreeSWITCH")
    esl_con.events("plain", "CHANNEL_HANGUP")
    while True:
        e = esl_con.recvEventTimed(1)  # 1 second timeout
        if e:
            event_name = e.getHeader("Event-Name")
            #print("Checking for hangup")
            if event_name == "CHANNEL_HANGUP":
                call_id = e.getHeader("Unique-ID")
                if call_id:
                    matching_key = None
                    for key in redis_client.keys("calldata:*"):
                        data = redis_client.get(key)
                        if data:
                            try:
                                data_dict = json.loads(data)
                                if isinstance(data_dict, dict) and data_dict.get("uuid") == call_id:
                                    matching_key = key
                                    break
                            except json.JSONDecodeError:
                                print(f"Error decoding JSON from Redis for key {key}")
                    
                    if matching_key:
                        redis_client.delete(matching_key)
                        print(f"[Pusher] Removed message {matching_key} from Redis due to hangup event")


def pusher():
    while True:
        queue = rabbitmq_channel.queue_declare(queue=os.getenv('RABBIT_MQ_QUEUE'), passive=True)
        if queue.method.message_count == 0 and queue.method.consumer_count > 0:
            esl_con = ESL.ESLconnection(os.getenv('ESL_HOST'), os.getenv('ESL_PORT'), os.getenv('ESL_PASSWORD'))
            if not esl_con.connected():
                raise Exception("Failed to connect to FreeSWITCH")
            last_id, call_data, uuid = get_last_stored_calldata()
            # print("Stopping queue music")
            esl_con.api("uuid_break", uuid)
            if call_data:
                rabbitmq_channel.basic_publish(exchange='', routing_key=os.getenv('RABBIT_MQ_QUEUE'), body=call_data)
                print(f"[Pusher] Moved message {last_id} from Redis to RabbitMQ")
                redis_client.delete(last_id)
            else:
                # print("[Pusher] No messages in Redis to push")
                pass

def main():
    # while True:
    # f1 = loop.create_task(handle_hangup_event())
    # f2 = loop.create_task(pusher())
    # await asyncio.wait([f1, f2])
    thread1 = Thread(target=handle_hangup_event)
    thread2 = Thread(target=pusher)
    thread1.start()
    thread2.start()
    thread1.join()
    
    # thread2.join()
    
    # handle_hangup_event()

if __name__ == "__main__":
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(main())
    # loop.close()
    main()