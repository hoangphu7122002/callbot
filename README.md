# CallBot Containerized Services

This repository contains containerized services for the CallBot application, which handles call processing, speech recognition, and natural language responses.

## Components

- **Worker**: Processes incoming calls, handles voice activity detection, speech-to-text, and text-to-speech operations
- **Pusher**: Monitors call queues and moves calls from Redis to RabbitMQ when workers are available
- **RabbitMQ**: Message queue for call processing

## Requirements

- Docker
- Docker Compose
- OpenAI API key for LLM and TTS
- FreeSWITCH instance (for call handling)
- Redis (for call data storage)
- PostgreSQL (for call activity logging)

## Setup

1. Copy the environment file and configure it:
   ```bash
   cp .env.example .env
   ```
   Edit the `.env` file and set all required values, especially:
   - `OPENAI_API_KEY`
   - Database connection settings
   - FreeSWITCH connection settings

2. Make sure the `records` and `src` directories exist:
   ```bash
   mkdir -p records
   ```

3. Start the services:
   ```bash
   docker-compose up -d
   ```

## Scaling

You can adjust the number of worker instances by changing the `replicas` value in `docker-compose.yml` or using the `docker-compose up --scale` command:

```bash
docker-compose up -d --scale worker=5 --scale pusher=1
```

## Logs

View logs for all services:
```bash
docker-compose logs -f
```

View logs for a specific service:
```bash
docker-compose logs -f worker
docker-compose logs -f pusher
docker-compose logs -f rabbitmq
```

## Architecture

- **RabbitMQ**: Handles the queue of incoming calls
- **Pusher**: Moves calls from Redis to RabbitMQ when workers are available
- **Worker**: Processes the calls, running voice detection, ASR, LLM, and TTS

## Environment Variables

See `.env.example` for a full list of required environment variables and their descriptions.

## Troubleshooting

- Check container logs for errors
- Ensure RabbitMQ, Redis, and PostgreSQL are accessible from the containers
- Verify FreeSWITCH ESL connection settings

## Additional Information

The worker and pusher services require the following directories to be mounted:
- `src/`: Contains the source code for speech processing, database handling, etc.
- `records/`: Directory for storing call recordings and other data 