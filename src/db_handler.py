import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import psycopg2
import logging
import os
import redis
import json
from datetime import datetime
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv

# Setup paths and environment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
dotenv_path = os.path.join(ROOT_DIR, ".env")
load_dotenv(dotenv_path)

class DBHandler:
    def __init__(self, init_postgres=False, init_redis=False, init_minio=False):
        """Initialize database handler with optional connection initialization.
        
        Args:
            init_postgres (bool): Whether to initialize PostgreSQL connection
            init_redis (bool): Whether to initialize Redis connection
            init_minio (bool): Whether to initialize MinIO connection
        """
        self.pg_config = None
        self.redis_client = None
        self.minio_client = None
        self.minio_bucket = None
        self.record_path = None
        
        # Initialize only requested connections
        if init_postgres:
            self._init_postgres_config()
        
        if init_redis:
            self._init_redis_config()
            
        if init_minio:
            self._init_minio_config()
        
    def _init_postgres_config(self):
        """Initialize PostgreSQL configuration."""
        logging.info("Initializing PostgreSQL configuration")
        self.pg_config = {
            'dbname': os.getenv('POSTGRES_DB'),
            'user': os.getenv('POSTGRES_USER'),
            'password': os.getenv('POSTGRES_PASSWORD'),
            'host': os.getenv('POSTGRES_HOST'),
            'port': int(os.getenv('POSTGRES_PORT', '5432'))
        }
        
    def _init_redis_config(self):
        """Initialize Redis configuration and connection."""
        logging.info("Initializing Redis connection")
        try:
            self.redis_client = redis.StrictRedis(
                host=os.getenv('REDIS_HOST'),
                port=int(os.getenv('REDIS_PORT', '6379')),
                db=0,
                decode_responses=True
            )
            logging.info("Redis connection initialized")
        except Exception as e:
            logging.error(f"Error initializing Redis connection: {e}")
            self.redis_client = None
            
    def _init_minio_config(self):
        """Initialize MinIO configuration and client."""
        logging.info("Initializing MinIO connection")
        try:
            self.minio_client = Minio(
                endpoint=os.getenv('MINIO_HOST'),
                access_key=os.getenv('MINIO_ACCESS_KEY'),
                secret_key=os.getenv('MINIO_SECRET_KEY'),
                secure=False
            )
            self.minio_bucket = os.getenv('MINIO_BUCKET_NAME')
            self.record_path = os.getenv('RECORD_PATH')
            
            logging.info(f"MinIO bucket: {self.minio_bucket}, record path: {self.record_path}")
            logging.info("MinIO client initialized")
            
        except Exception as e:
            logging.error(f"Error initializing MinIO client: {e}")
            self.minio_client = None
            
    def _get_postgres_connection(self):
        """Get a PostgreSQL connection."""
        if not self.pg_config:
            logging.warning("PostgreSQL configuration not initialized")
            self._init_postgres_config()
            
        try:
            return psycopg2.connect(**self.pg_config)
        except Exception as e:
            logging.error(f"Error connecting to PostgreSQL: {e}")
            return None
    
    def _ensure_redis_client(self):
        """Ensure Redis client is initialized."""
        if not self.redis_client:
            logging.warning("Redis client not initialized, initializing now")
            self._init_redis_config()
        return self.redis_client is not None
    
    def _ensure_minio_client(self):
        """Ensure MinIO client is initialized."""
        if not self.minio_client:
            logging.warning("MinIO client not initialized, initializing now")
            self._init_minio_config()
        return self.minio_client is not None
    
    def insert_call_activity(self, uuid, number, step, output, processing_time):
        """Insert call activity data into PostgreSQL database."""
        try:
            conn = self._get_postgres_connection()
            if not conn:
                return False
                
            now = datetime.now()
            cursor = conn.cursor()
            
            insert_query = """
                INSERT INTO callbot.activity_history (uuid, number, step, output, processing_time, time)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            payload = (uuid, number, step, output, processing_time, now)
            cursor.execute(insert_query, payload)
            conn.commit()
            cursor.close()
            conn.close()
            
            logging.info(f"Inserted call activity: {uuid}, {step}")
            return True
            
        except Exception as e:
            logging.error(f"Error inserting call activity: {e}")
            return False
            
    def store_call_data(self, call_data):
        """Store call data in Redis."""
        if not self._ensure_redis_client():
            return False
            
        try:
            key = f"calldata:{call_data['uuid']}"
            self.redis_client.set(key, json.dumps(call_data))
            logging.info(f"Stored call data in Redis: {key}")
            return True
            
        except Exception as e:
            logging.error(f"Error storing call data in Redis: {e}")
            return False
            
    def get_call_data(self, key):
        """Get call data from Redis by key."""
        if not self._ensure_redis_client():
            return None
            
        try:
            data_str = self.redis_client.get(key)
            if data_str:
                try:
                    # Properly decode the JSON data
                    return json.loads(data_str)
                except json.JSONDecodeError as json_err:
                    logging.error(f"JSON parsing error for key {key}: {json_err}")
                    # Leave data as is if it can't be parsed as JSON
                    return data_str
            return data_str
            
        except Exception as e:
            logging.error(f"Error getting call data from Redis: {e}")
            return None
            
    def get_last_stored_call_data(self):
        """Get the last stored call data from Redis."""
        if not self._ensure_redis_client():
            return None, None, None
            
        try:
            keys = self.redis_client.keys("calldata:*")
            if not keys:
                return None, None, None
                
            last_id = sorted(keys)[-1]  # Get the last stored key
            call_data_str = self.redis_client.get(last_id)
            
            if call_data_str:
                try:
                    # Safely parse the JSON data
                    call_data_dict = json.loads(call_data_str)
                    uuid = call_data_dict.get("uuid")
                    return last_id, call_data_str, uuid
                except json.JSONDecodeError as json_err:
                    logging.error(f"JSON parsing error for key {last_id}: {json_err}")
                    # Try to handle existing data that might have been stored as Python string
                    if isinstance(call_data_str, str) and call_data_str.startswith("{'uuid'"):
                        # Try to extract the UUID from the malformed string using string operations
                        import re
                        uuid_match = re.search(r"'uuid':\s*'([^']+)'", call_data_str)
                        if uuid_match:
                            uuid = uuid_match.group(1)
                            return last_id, call_data_str, uuid
            
            return last_id, call_data_str, None
            
        except Exception as e:
            logging.error(f"Error getting last stored call data: {e}")
            return None, None, None
            
    def remove_call_data(self, key):
        """Remove call data from Redis by key."""
        if not self._ensure_redis_client():
            return False
            
        try:
            self.redis_client.delete(key)
            logging.info(f"Removed call data from Redis: {key}")
            return True
            
        except Exception as e:
            logging.error(f"Error removing call data from Redis: {e}")
            return False
            
    def upload_audio_to_minio(self, uuid):
        """Upload audio file to MinIO storage."""
        if not self._ensure_minio_client():
            return False
            
        try:
            # Simple path construction like in the original version
            final_audio_file = f"{self.record_path}/{uuid}.wav"
            audio_file = f"{uuid}.wav"
            
            # Log basic info
            logging.info(f"Uploading audio file: {final_audio_file}")
            
            # Check if the bucket exists and create if it doesn't
            if not self.minio_client.bucket_exists(self.minio_bucket):
                self.minio_client.make_bucket(self.minio_bucket)
                logging.info(f"Created MinIO bucket: {self.minio_bucket}")
                
            # Upload the file - simple approach like the original
            self.minio_client.fput_object(self.minio_bucket, audio_file, final_audio_file)
            logging.info(f"Successfully uploaded audio file to MinIO: {audio_file}")
            return True
            
        except Exception as e:
            logging.error(f"Error uploading file to MinIO: {e}")
            return False 