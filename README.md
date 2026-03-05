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
Each tool is implemented as a module and placed in the `tools/` directory.

Tools must implement a standard interface:
- name
- description
- parameters
- execute()
The agent dynamically loads all tools at startup.
Example:
```
tools/
  home_assistant.py
  rss_reader.py
  calendar.py
```
