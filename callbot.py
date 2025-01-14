"""
Python CallBot - A voice-enabled chatbot that integrates with SIP telephony via Java
This module handles speech-to-text, chatbot interaction, and text-to-speech conversion
"""

import asyncio
import socket
import json
import base64
import websockets
from src.audio_handler import AudioHandler
from src.speech_processor import SpeechProcessor
from src.chatbot_client import ChatbotClient
from config.config import config

class SipCallBot:
    """
    Main CallBot class that handles:
    1. Connection with Java SIP server
    2. Audio processing
    3. Speech-to-text and text-to-speech conversion
    4. Chatbot interaction
    """

    def __init__(self):
        # Connection settings for Java SIP server
        self.java_host = 'localhost'
        self.java_port = 5000
        self.socket = None
        self.is_connected = False
        self.is_in_call = False  # Track if currently in a call
        
        # Initialize audio processing components
        self.audio_handler = AudioHandler(
            chunk=config.AUDIO_CHUNK,
            channels=config.AUDIO_CHANNELS,
            rate=config.AUDIO_RATE,
            silence_threshold=config.SILENCE_THRESHOLD,
            silence_chunks=config.SILENCE_CHUNKS,
            initial_silence_chunks=config.INITIAL_SILENCE_CHUNKS
        )
        self.speech_processor = SpeechProcessor()
        self.chatbot = ChatbotClient(config)

    async def connect_to_java(self):
        """
        Establish TCP connection with Java SIP server
        Returns True if connection successful, False otherwise
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.java_host, self.java_port))
            self.is_connected = True
            print("Connected to Java SIP server")
            
            # Send connection confirmation
            message = "CONNECTED\n"
            self.socket.sendall(message.encode())
            
            # Start listening for SIP events
            await self.listen_for_sip_events()
            return True
        except Exception as e:
            print(f"Failed to connect to Java server: {e}")
            self.is_connected = False
            return False

    async def listen_for_sip_events(self):
        """
        Listen for events from Java SIP server:
        - CALL_START: New call initiated
        - CALL_END: Call terminated
        """
        while self.is_connected:
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self.socket.recv, 1024)
                if not data:
                    break

                message = data.decode().strip()
                if message.startswith("CALL_START:"):
                    # New call notification received
                    call_id = message.split(":")[1]
                    print(f"Call started with ID: {call_id}")
                    self.is_in_call = True
                    # Start call handling
                    await self.handle_call()
                elif message == "CALL_END":
                    # Call end notification received
                    print("Call ended")
                    self.is_in_call = False

            except Exception as e:
                print(f"Error in listening for SIP events: {e}")
                self.is_connected = False
                break

    async def handle_call(self):
        """
        Handle active call:
        1. Send welcome message
        2. Process incoming audio
        3. Generate and send responses
        4. Monitor for call end conditions
        """
        print("Starting call handling...")
        
        # Send welcome message
        welcome_message = "Hello, I'm an AI assistant. How can I help you?"
        welcome_audio = await self.text_to_speech(welcome_message)
        if welcome_audio:
            await self.send_audio(welcome_audio)

        while self.is_in_call:
            try:
                # Record audio from microphone
                audio_data = self.audio_handler.record_audio()
                if audio_data is None:
                    continue

                # Convert speech to text
                user_text = await self.speech_processor.speech_to_text(audio_data)
                if not user_text:
                    continue

                print(f"User: {user_text}")

                # Check for end call keywords
                if self.should_end_call(user_text):
                    print("User requested to end call")
                    goodbye_message = "Thank you for talking. Goodbye!"
                    goodbye_audio = await self.text_to_speech(goodbye_message)
                    if goodbye_audio:
                        await self.send_audio(goodbye_audio)
                    # Send end call signal
                    await self.send_end_call_signal()
                    break

                # Get chatbot response
                bot_response = await self.chatbot.get_response(user_text)
                print(f"Bot: {bot_response}")

                # Convert response to speech
                audio_response = await self.text_to_speech(bot_response)
                if audio_response:
                    await self.send_audio(audio_response)

            except Exception as e:
                print(f"Error in call handling: {e}")
                break

        print("Call handling ended")

    async def send_audio(self, audio_data):
        """Send audio data to Java SIP server"""
        if self.is_connected and self.is_in_call:
            try:
                audio_base64 = base64.b64encode(audio_data).decode()
                message = f"AUDIO:{audio_base64}\n"
                self.socket.sendall(message.encode())
            except Exception as e:
                print(f"Error sending audio: {e}")

    async def send_end_call_signal(self):
        """Send signal to end current call"""
        if self.is_connected:
            try:
                message = "END_CALL\n"
                self.socket.sendall(message.encode())
            except Exception as e:
                print(f"Error sending end call signal: {e}")

    def should_end_call(self, text):
        """Check if text contains end call keywords"""
        end_keywords = ['goodbye', 'bye', 'end call', 'hang up']
        return any(keyword in text.lower() for keyword in end_keywords)

    async def text_to_speech(self, text):
        """
        Convert text to speech using websocket TTS service
        Returns audio data in bytes or None if conversion fails
        """
        try:
            async with websockets.connect(config.TTS_WEBSOCKET_URL) as websocket:
                request_data = {
                    "text": text,
                    "language": config.TTS_LANGUAGE,
                    "sample_file": config.TTS_VOICE
                }
                await websocket.send(json.dumps(request_data))
                
                audio_data = bytearray()
                
                while True:
                    try:
                        response = await websocket.recv()
                        data = json.loads(response)
                        
                        if "error" in data:
                            print(f"Error: {data['error']}")
                            break
                            
                        if data.get("status") == "error":
                            print(f"Error processing text: {data.get('error')}")
                            continue
                            
                        chunk = base64.b64decode(data["audio_base64"])
                        audio_data.extend(chunk)
                        
                        if data["index"] == data["total"] - 1:
                            return bytes(audio_data)
                            
                    except websockets.exceptions.ConnectionClosed:
                        print("WebSocket connection closed")
                        break
                        
        except Exception as e:
            print(f"Error in text-to-speech processing: {e}")
            return None

    async def run(self):
        """
        Main run loop:
        1. Attempt to connect to Java SIP server
        2. If connected, listen for events
        3. If disconnected, retry connection
        """
        while True:
            if not self.is_connected:
                if await self.connect_to_java():
                    await asyncio.sleep(1)
                else:
                    print("Retrying connection in 5 seconds...")
                    await asyncio.sleep(5)

async def main():
    """Initialize and run the CallBot"""
    bot = SipCallBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main()) 