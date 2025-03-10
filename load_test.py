from locust import User, task, between
import asyncio
import wave
import io
from pydub import AudioSegment
from src.speech_processor import SpeechProcessor
from src.chatbot_client import ChatbotClient
from src.text_normalizer import TextNormalizer
from config.config import config
import time
import logging
import uuid
import random
import re

import nest_asyncio
nest_asyncio.apply()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('load_test.log'),
        logging.StreamHandler()
    ]
)

class CallSimulator:
    def __init__(self, fixed_rounds=None):
        self.speech_processor = SpeechProcessor()
        self.chatbot = ChatbotClient(config)
        self.text_normalizer = TextNormalizer()
        self.welcome_file = "/home/hm1905/records/welcome_chao.wav"
        self.processing_file = "/home/hm1905/records/processing.wav"
        self.fixed_rounds = fixed_rounds
        
        # List các file audio test
        self.test_audio_files = [
            "/home/hm1905/records/welcome1.wav",
            "/home/hm1905/records/welcome2.wav",
            "/home/hm1905/records/welcome3.wav",
            "/home/hm1905/records/welcome4.wav",
            "/home/hm1905/records/welcome5.wav"
        ]

    async def simulate_playback(self, audio_segment):
        """Simulate audio playback by waiting for the duration of the audio"""
        playback_duration = len(audio_segment) / 1000.0
        await asyncio.sleep(playback_duration)
        return playback_duration

    async def play_welcome_message(self):
        """Play welcome message"""
        audio = AudioSegment.from_wav(self.welcome_file)
        await self.simulate_playback(audio)

    async def play_processing_message(self):
        """Play processing message"""
        audio = AudioSegment.from_wav(self.processing_file)
        await self.simulate_playback(audio)

    async def simulate_network_delay(self, audio_path):
        """Simulate network delay including audio processing time"""
        audio = AudioSegment.from_wav(audio_path)
        audio_duration = len(audio) / 1000.0  # Convert to seconds
        network_latency = random.uniform(0.05, 0.15)
        total_delay = audio_duration + network_latency
        await asyncio.sleep(total_delay)
        return total_delay

    async def process_audio(self, audio_data, audio_path, round_num):
        """Process audio and generate response"""
        try:
            metrics = {
                'asr_time': 0,
                'llm_time': 0,
                'tts_time': 0,
                'playback_time': 0,
                'processing_time': 0,
                'network_delay': 0,
                'total_time': 0
            }
            
            start_time = time.time()

            # Simulate network delay in parallel with main processing
            delay_task = asyncio.create_task(self.simulate_network_delay(audio_path))
            
            # Create main processing task
            async def main_processing():
                # ASR
                asr_start = time.time()
                user_text = await self.speech_processor.speech_to_text(audio_data)
                metrics['asr_time'] = time.time() - asr_start
                
                if not user_text:
                    return None

                # LLM
                llm_start = time.time()
                hardprompt = f"""
                You are a VCBS callbot, respond briefly and concisely, minimize punctuation marks like . or , respond politely, address users as anh chị.
                Note the following facts:
                - Tô Lâm is the President of Vietnam
                - Hoàng Sa, Trường Sa belong to Vietnam
                This is round {round_num} of the conversation.
                Also pay attention to conversation history context.

                Please don't generate some sign like: '.', ',', '*' and number of word approximates 100 words. 
                User's question is: """
                
                bot_response = await self.chatbot.get_response(hardprompt + user_text)
                normalized_response = self.text_normalizer.normalize_vietnamese_text(bot_response)
                metrics['llm_time'] = time.time() - llm_start
                
                return normalized_response

            # Run all tasks in parallel
            processing_task = asyncio.create_task(self.play_processing_message())
            main_task = asyncio.create_task(main_processing())
            
            # Wait for network delay
            await delay_task
            metrics['network_delay'] = time.time() - start_time
            
            # Wait for processing tasks
            done, pending = await asyncio.wait(
                [processing_task, main_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            try:
                # If processing_task completed first, wait for main_task
                if processing_task in done:
                    response_text = await main_task
                    metrics['processing_time'] = time.time() - start_time
                else:
                    # If main_task completed first, cancel processing_task
                    if not processing_task.done():
                        processing_task.cancel()
                    response_text = main_task.result()
                    metrics['processing_time'] = time.time() - start_time

                    # Chờ processing_task kết thúc an toàn
                    if not processing_task.done():
                        try:
                            await processing_task
                        except (asyncio.CancelledError, Exception):
                            pass

                # Clean up any remaining tasks
                for task in pending:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except (asyncio.CancelledError, Exception):
                            pass

            except Exception as e:
                # Ensure all tasks are properly cancelled
                for task in [processing_task, main_task]:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except (asyncio.CancelledError, Exception):
                            pass
                raise e

            if not response_text:
                return metrics

            # TTS
            tts_start = time.time()

            response_text = response_text.replace("*","").replace("**","")
            response_text = re.sub(r'\s+', ' ', response_text)
            audio_segment = await self.speech_processor.text_to_speech(response_text)

            metrics['tts_time'] = time.time() - tts_start
            
            # Simulate response playback
            playback_start = time.time()
            await self.simulate_playback(audio_segment)
            metrics['playback_time'] = time.time() - playback_start
            
            metrics['total_time'] = time.time() - start_time
            return metrics
            
        except Exception as e:
            logging.error(f"Error processing audio: {e}")
            return None

    async def process_call(self):
        try:
            call_id = str(uuid.uuid4())
            
            # Determine number of rounds
            if self.fixed_rounds is not None:
                num_rounds = self.fixed_rounds
            else:
                num_rounds = random.randint(3, 7)
            
            all_metrics = []
            total_start_time = time.time()
            
            # Play welcome message first
            await self.play_welcome_message()
            
            for round_num in range(1, num_rounds + 1):
                await asyncio.sleep(random.uniform(1, 2))
                
                # Load test audio
                test_audio_path = random.choice(self.test_audio_files)
                with wave.open(test_audio_path, 'rb') as wav_file:
                    audio_data = wav_file.readframes(wav_file.getnframes())
                
                metrics = await self.process_audio(audio_data, test_audio_path, round_num)
                if metrics:
                    metrics['round_num'] = round_num
                    all_metrics.append(metrics)
            
            # Calculate aggregate metrics
            aggregate_metrics = {
                'num_rounds': num_rounds,
                'asr_time': sum(m['asr_time'] for m in all_metrics),
                'llm_time': sum(m['llm_time'] for m in all_metrics),
                'tts_time': sum(m['tts_time'] for m in all_metrics),
                'playback_time': sum(m['playback_time'] for m in all_metrics),
                'processing_time': sum(m['processing_time'] for m in all_metrics),
                'network_delay': sum(m['network_delay'] for m in all_metrics),
                'total_time': time.time() - total_start_time
            }
            
            return aggregate_metrics, all_metrics
            
        except Exception as e:
            logging.error(f"Error in process_call: {e}")
            return None, None

class CallBotUser(User):
    wait_time = between(1, 2)
    
    def on_start(self):
        self.simulator = CallSimulator(fixed_rounds=1)
    
    @task
    def simulate_call(self):
        try:
            # Tạo event loop mới cho mỗi lần gọi
            # loop = asyncio.new_event_loop()
            # asyncio.set_event_loop(loop)
            
            try:
                aggregate_metrics, round_metrics = asyncio.run(
                    self.simulator.process_call()
                )
            finally:
                # Đảm bảo đóng loop sau khi sử dụng
                # loop.close()
                asyncio.set_event_loop(None)
            
            if aggregate_metrics and round_metrics:
                # Report aggregate metrics
                self.environment.events.request.fire(
                    request_type="TOTAL",
                    name=f"Complete Call ({aggregate_metrics['num_rounds']} rounds)",
                    response_time=aggregate_metrics['total_time'] * 1000,
                    response_length=0,
                    exception=None,
                )
                
                # Report individual round metrics
                for metrics in round_metrics:
                    round_num = metrics['round_num']
                    
                    self.environment.events.request.fire(
                        request_type="ASR",
                        name=f"Speech-to-Text (Round {round_num})",
                        response_time=metrics['asr_time'] * 1000,
                        response_length=0,
                        exception=None,
                    )
                    
                    self.environment.events.request.fire(
                        request_type="LLM",
                        name=f"Chat Response (Round {round_num})",
                        response_time=metrics['llm_time'] * 1000,
                        response_length=0,
                        exception=None,
                    )
                    
                    self.environment.events.request.fire(
                        request_type="TTS",
                        name=f"Text-to-Speech (Round {round_num})",
                        response_time=metrics['tts_time'] * 1000,
                        response_length=0,
                        exception=None,
                    )
                    
                    self.environment.events.request.fire(
                        request_type="PLAYBACK",
                        name=f"Audio Playback (Round {round_num})",
                        response_time=metrics['playback_time'] * 1000,
                        response_length=0,
                        exception=None,
                    )
                    
                    self.environment.events.request.fire(
                        request_type="PROCESSING",
                        name=f"Processing Message (Round {round_num})",
                        response_time=metrics['processing_time'] * 1000,
                        response_length=0,
                        exception=None,
                    )
                    
                    # Report network delay metric
                    self.environment.events.request.fire(
                        request_type="NETWORK_DELAY",
                        name=f"Network Delay (Round {round_num})",
                        response_time=metrics['network_delay'] * 1000,
                        response_length=0,
                        exception=None,
                    )
                
        except Exception as e:
            logging.error(f"Error in simulate_call: {e}") 
