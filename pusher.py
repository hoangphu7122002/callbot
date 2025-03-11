import pika
import redis
import json
import time
#from threading import Thread
from freeswitchESL import ESL
import asyncio


# Redis Configuration
redis_client = redis.StrictRedis(host='localhost', port=6380, db=0, decode_responses=True)

# RabbitMQ Configuration
rabbitmq_connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
rabbitmq_channel = rabbitmq_connection.channel()
rabbitmq_channel.queue_declare(queue='call_queue', durable=True)

#ESL Configuration
esl_con = ESL.ESLconnection("127.0.0.1", "8021", "ClueCon")
print("Connect ESL Successfully")
if not esl_con.connected():
    raise Exception("Failed to connect to FreeSWITCH")

async def get_last_stored_calldata():
    keys = redis_client.keys("calldata:*")
    if keys:
        last_id = sorted(keys)[-1]  # Get the last stored message
        call_data = redis_client.get(last_id)
        return last_id, call_data
    return None, None

async def handle_hangup_event():
    esl_con.events("plain", "CHANNEL_HANGUP")
    print("Listening for HANGUP")
    while True:
        await asyncio.sleep(1)  # GAP TIME
        e = esl_con.recvEvent()
        if e:
            event_name = e.getHeader("Event-Name")
            print("Checking for hangup")
            if event_name == "CHANNEL_HANGUP":
                call_id = e.getHeader("Unique-ID")
                if call_id and redis_client.exists(f"calldata:{call_id}"):
                    redis_client.delete(f"calldata:{call_id}")
                    print(f"[Pusher] Removed message {call_id} from Redis due to hangup event")

async def pusher():
    while True:
        await asyncio.sleep(5)  # GAP TIME
        queue = rabbitmq_channel.queue_declare(queue='call_queue', passive=True)
        if queue.method.message_count == 0 and queue.method.consumer_count > 0:
            last_id, call_data = get_last_stored_calldata()
            if call_data:
                rabbitmq_channel.basic_publish(exchange='', routing_key='call_queue', body=call_data)
                print(f"[Pusher] Moved message {last_id} from Redis to RabbitMQ")
                redis_client.delete(last_id)
            else:
                print("[Pusher] No messages in Redis to push")

async def main():
    await asyncio.gather(
        handle_hangup_event(),
        pusher()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
