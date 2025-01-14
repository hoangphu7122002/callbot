import websockets
import asyncio
import json

async def callbot_client():
    uri = "ws://localhost:5062"
    async with websockets.connect(uri) as websocket:
        # Đăng ký với Kamailio
        register_msg = {
            "method": "REGISTER",
            "from": "sip:bot@callbot.local",
            "contact": "<sip:bot@127.0.0.1:5080>",
            "expires": 3600
        }
        await websocket.send(json.dumps(register_msg))
        
        # Lắng nghe các cuộc gọi đến
        while True:
            msg = await websocket.recv()
            data = json.loads(msg)
            
            if data.get("method") == "INVITE":
                # Xử lý cuộc gọi đến
                print(f"Incoming call from: {data.get('from')}")
                
                # Gửi response chấp nhận cuộc gọi
                accept_msg = {
                    "method": "200 OK",
                    "call-id": data.get("call-id"),
                    "to": data.get("from"),
                    "from": "sip:bot@callbot.local"
                }
                await websocket.send(json.dumps(accept_msg))

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(callbot_client()) 