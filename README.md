# Jot-two
A rebuild of '[Jot](https://github.com/Kalekdan/jot)' designed to be more scaleable, and built with some of the learnings from the first Jot.

Implements many of the same functionalities of Jot. Primary enhancements include:
- Tools becoming more modular
  - Should be able to add tools without needing to change any of the code, just drop in a new module
- Less sequential
  - Jot was very sequential in it's processing, would wait for one thing to happen before the next would start. Needs to be able to support multiple activities running in parallel, and make use of streaming where possible
- More inputs
  - Jot only allowed voice input, but I would like to be able to interface with Jot from anywhere

## Design Principles

Jot-two is built around a few key principles:

- Event-driven architecture
- Modular tool system
- Multi-channel interaction
- Self-hostable
- Asynchronous processing

## High Level Design
### Processing Flow

The system follows an event-driven architecture.

1. Input adapters receive messages from external systems.
2. Each message is converted into the standard message format.
3. The message is pushed to the **Input Queue**.
4. The **Processing Layer** consumes the request.
5. The processing layer may invoke one or more **tool modules**.
6. A response message is created and pushed to the **Output Queue**.
7. The **Output Router** sends the response to the appropriate destination.

<img width="600" alt="image" src="https://github.com/user-attachments/assets/21e059e4-76bd-4aa8-9764-0478630673ba" />

### Technologies
Jot-two will be primarily built in Python, using Redis Streams for queing messages. Any web interface (if needed) will be built in React.JS.

### Input Interface
All input interface adapters will produce a standard JSON output as follows:
``` JSON
{
   "request_id":"uuid-123",
   "source":"whatsapp",
   "user_id":"user_42",
   "reply_channel":"whatsapp", // optional: if not provided, defaults to source
   "timestamp":1710000000,
   "payload":{
      "text":"Turn the lights on"
   }
}
```
This is sent to the input queue to be picked up by the agent.

### Tool System
Tools provide the assistant with the ability to interact with external systems.
Each tool is implemented as a module and placed in the `src/agent/tools/` directory.
Each module can expose one or many tools (for example, `weather.py` can include `get_current_weather` and `get_future_weather`).

Tools must implement a standard interface:
- name
- description
- parameters
- execute()
The agent dynamically discovers and loads all tools at startup, then exposes them to the LLM through function-calling so tools can be selected and executed automatically.
Example:
```
src/agent/tools/
  home_assistant.py
  rss_reader.py
  calendar.py
```

### LLM Delivery Architecture
To ensure the bot retains context of what is said and conversation history, each payload sent to the LLM includes the following:
- *System Prompt* - The first message defining the rules of the assistant
- *A conversation summary* - Every 20 (configurable) messages, a summary is updated and this is sent to the LLM as well
- *Retrieved memory* - From a vector DB, to get any additional relevant context. A classic RAG approach
- *Recent messages* - the past 5 (configurable) messages sent are included
- *User message* - the actual user request

Conversation messages and summaries are persisted in PostgreSQL. Recent message retrieval and latest-summary lookup are read from the database instead of in-memory state.


## Repository Structure
```
src/
  adapters/        # input adapters
  agent/           # core assistant logic
  core/            # shared message models
  tools/           # modular tool implementations
  router/          # output router
  main.py          # async event pipeline entrypoint
```


### Run Locally

Recommended run with docker-compose.yml
```bash
docker compose up --build
```

## Adding New Input Adapters

Input adapters are auto-discovered from `src/adapters/` at startup.

To add a new adapter, create a new module in `src/adapters/` and define a class that:

- Inherits from `BaseInputAdapter` (`src/adapters/base.py`)
- Accepts `input_queue` and `stop_event` in `__init__`
- Implements `async def run(self) -> None`
- Pushes normalized `Message` objects to `input_queue`

No changes are required outside `src/adapters/` for adapter registration.


### Required Environment Variables
To be set in the .env file
- `TELEGRAM_BOT_TOKEN`: Telegram bot token from BotFather
- `OPENAI_API_KEY`: API key for your OpenAI-compatible endpoint

The below need to be populated, but can be left as default and will be autopopulated.
- `DATABASE_URL`: PostgreSQL DSN used by `jot-core` to persist conversation messages and summaries
- `POSTGRES_DB`: PostgreSQL database name for docker-compose setup
- `POSTGRES_USER`: PostgreSQL username for docker-compose setup
- `POSTGRES_PASSWORD`: PostgreSQL password for docker-compose setup
- `OPENAI_BASE_URL` (default `https://api.openai.com`): provider base URL
- `OPENAI_CHAT_ENDPOINT` (default `/v1/chat/completions`): chat completion path
- `OPENAI_MODEL` (default `gpt-5-nano`): model identifier
- `OPENAI_SYSTEM_PROMPT_FILE`: path to the text file containing the system prompt
- `OPENAI_TIMEOUT_SECONDS` (default `60`): HTTP timeout for model calls

### Optional Environment Variables
To be set in the .env file
- `TELEGRAM_POLL_TIMEOUT` (default `20`): long-poll timeout in seconds for `getUpdates`
- `TELEGRAM_RETRY_DELAY` (default `2`): delay before retrying after Telegram API errors
- `OPENAI_SUMMARY_EVERY_MESSAGES` (default `10`): refresh summary after this many new conversation messages
- `OPENAI_RECENT_MESSAGES_LIMIT` (default `10`): number of recent messages included in each request
- `OPENAI_MAX_TOOL_ROUNDS` (default `5`): max tool-call rounds per user message before stopping
- `OPENWEATHERMAP_API_KEY`: API key used by the weather tool
- `OPENWEATHERMAP_BASE_URL` (default `https://api.openweathermap.org/data/2.5/weather`): weather endpoint override
- `OPENWEATHERMAP_FORECAST_BASE_URL` (default `https://api.openweathermap.org/data/2.5/forecast`): forecast endpoint override
- `OPENWEATHERMAP_TIMEOUT_SECONDS` (default `10`): HTTP timeout used by the weather tool
### Docker Compose Usage

```bash
docker compose up --build
```

## Web UI (Jot-two Manager)

A web-based management interface is available at **http://localhost:8080** when running with Docker Compose.

### Dashboard

The dashboard provides a real-time overview of the system:

- **Service Status** — connectivity indicators for Redis, PostgreSQL, and each Docker container
- **Redis Streams** — message volumes, consumer groups, and recent message sources for `jot:input` and `jot:output`
- **PostgreSQL Tables** — lists all tables with row counts; click any table to expand and inspect its rows

### Chat

The **Chat** page connects directly to Jot-two via a WebSocket. Messages are submitted with `web-app` as the source and replies are streamed back in real time.

### Running the Web UI standalone (development)

The frontend dev server proxies API and WebSocket calls to the backend, so you can run both separately:

```bash
# Terminal 1 — Python backend (requires Redis + PostgreSQL running)
pip install -r requirements.txt
python -m src.main_webapp

# Terminal 2 — React frontend with hot reload
cd web-app
npm install
npm run dev
```

The dev server will be available at **http://localhost:5173** and proxies `/api` and `/ws` to `localhost:8080`.

