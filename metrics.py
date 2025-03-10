from prometheus_client import Counter, Gauge, Histogram, Summary
import prometheus_client

# Initialize metrics server
prometheus_client.start_http_server(18000)  # Metrics will be available on port 8000

# Overall system metrics
activate_calls = Gauge('callbot_active_calls','Number of active calls')
completed_calls = Gauge('callbot_completed_calls','Number of completed calls')
call_duration = Histogram('callbot_call_duration_seconds','Duration of calls in seconds')

# Latency metrics
asr_processing_time = Histogram('callbot_asr_processing_seconds','ASR processing time in seconds')
llm_processing_time = Histogram('callbot_llm_processing_seconds','LLM processing time in seconds')
tts_processing_time = Histogram('callbot_tts_processing_seconds','TTS processing time in seconds')
end_to_end_latency = Histogram('callbot_e2e_latency_seconds','End-to-end latency in seconds')

# Error metrics
asr_errors = Counter('callbot_asr_errors_total','Total number of ASR errors', ['error_type'])
llm_errors = Counter('callbot_llm_errors_total','Total number of LLM errors', ['error_type'])
tts_errors = Counter('callbot_tts_errors_total','Total number of TTS errors', ['error_type'])

# Worker metrics
worker_cpu_usage = Gauge('callbot_worker_cpu_percent', 'CPU usage of the worker process', ['worker_id'])
worker_memory_usage = Gauge('callbot_worker_memory_bytes', 'Memory usage of the worker process', ['worker_id'])
worker_calls_handled = Counter('callbot_worker_calls_total', 'Total calls handled by worker', ['worker_id'])

utterance_count = Counter('callbot_utterance_total', 'Total number of user utterances')
silence_count = Counter('callbot_silence_total', 'Total number of silence periods')
interrupt_count = Counter('callbot_interrupt_total', 'Total number of bot interruptions')