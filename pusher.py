import pika
import redis
import json
import time
from threading import Thread
from freeswitchESL import ESL
import asyncio


# Redis Configuration
redis_client = redis.StrictRedis(host='localhost', port=6380, db=0, decode_responses=True)

# RabbitMQ Configuration
rabbitmq_connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
rabbitmq_channel = rabbitmq_connection.channel()
rabbitmq_channel.queue_declare(queue='call_queue', durable=True)



def get_last_stored_calldata():
    keys = redis_client.keys("calldata:*")
    if keys:
        last_id = sorted(keys)[-1]  # Get the last stored message
        call_data = redis_client.get(last_id)
        return last_id, call_data
    return None, None

def handle_hangup_event():
    #ESL Configuration
    esl_con = ESL.ESLconnection("127.0.0.1", "8021", "ClueCon")
    print("Connect ESL Successfully")
    if not esl_con.connected():
        raise Exception("Failed to connect to FreeSWITCH")
    esl_con.events("plain", "CHANNEL_HANGUP")
    print("Listening for HANGUP")
    while True:
        #await asyncio.sleep(1)  # GAP TIME
        # print('hehe')
        e = esl_con.recvEventTimed(1)  # 1 second timeout
        # e = esl_con.recvEvent()
        print('e: ',e)
        # print('hihi')
        if e:
            event_name = e.getHeader("Event-Name")
            print("Checking for hangup")
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
        #await asyncio.sleep(5)  # GAP TIME
        print("Checking for open spot")
        queue = rabbitmq_channel.queue_declare(queue='call_queue', passive=True)
        if queue.method.message_count == 0 and queue.method.consumer_count > 0:
            last_id, call_data = get_last_stored_calldata()
            if call_data:
                rabbitmq_channel.basic_publish(exchange='', routing_key='call_queue', body=call_data)
                print(f"[Pusher] Moved message {last_id} from Redis to RabbitMQ")
                redis_client.delete(last_id)
            else:
                print("[Pusher] No messages in Redis to push")

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