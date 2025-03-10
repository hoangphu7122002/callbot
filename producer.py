import pika
import json
from freeswitchESL import ESL
import logging

# Thiết lập logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_to_queue(call_data):
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='call_queue')
    
    channel.basic_publish(exchange='', routing_key='call_queue', body=json.dumps(call_data))
    logging.info(f"Sent to queue: {call_data}")
    connection.close()

class CallListener:
    def __init__(self):
        self.esl_con = ESL.ESLconnection("127.0.0.1", "8021", "ClueCon")
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

if __name__ == "__main__":
    listener = CallListener()
    listener.listen_for_calls()
