# Tools

Tools are auto-discovered from `src/agent/tools/` at startup and exposed to the LLM as function-calling tools.

## Contract

Each tool must be a class that inherits from `BaseTool` and defines:

- `name`: unique function name exposed to the LLM
- `description`: short description of what the tool does
- `parameters`: JSON Schema object for tool arguments
- `async execute(**kwargs) -> dict[str, Any]`: returns JSON-serializable output

## Multiple Tools Per File

A single module can include multiple tool classes.

Example (`weather.py`):

- `GetCurrentWeatherTool` with `name = "get_current_weather"`
- `GetFutureWeatherTool` with `name = "get_future_weather"`

The loader discovers all eligible classes in each module and registers them individually.

## Naming Rules

- Tool names must be globally unique.
- Duplicate names will raise an error during startup.

## Environment Variables

Weather tools currently use:

- `OPENWEATHERMAP_API_KEY`
- `OPENWEATHERMAP_BASE_URL`
- `OPENWEATHERMAP_FORECAST_BASE_URL`
- `OPENWEATHERMAP_TIMEOUT_SECONDS`

Agent tool loop setting:

- `OPENAI_MAX_TOOL_ROUNDS`

## Quick Add Checklist

1. Create or update a module in `src/agent/tools/`.
2. Add one or more `BaseTool` subclasses.
3. Ensure each class has a unique `name`.
4. Implement `execute` and return a JSON-serializable dict.
5. Restart the app so tools are discovered on startup.
