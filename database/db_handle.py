from minio import Minio
from minio.error import S3Error
import psycopg2
from psycopg2 import sql


# MinIO server details. Seriously need to redo but lazy rn
minio_client = Minio(
    endpoint='xxxx:19000',  
    access_key='xxxx',
    secret_key='xxxx', 
    secure=False
)

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


#Postgres insert. Need Serious rework
def data_insert(uuid, number, step, output, processing_time):
    conn = psycopg2.connect(
      dbname="postgres", 
      user="postgres", 
      password="password", 
      host="xxxxxxx",
      port="35432" 
    )

    cursor = conn.cursor()
    insert_query = """
      INSERT INTO callbot.activity_history (uuid, number, step, output, processing_time)
      VALUES (%s, %s, %s, %s, %s)
    """
    payload = (uuid, number, step, output, processing_time)
    cursor.execute(insert_query, payload)
    conn.commit()
    cursor.close()
    conn.close()
