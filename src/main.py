from __future__ import annotations

import asyncio

from src.adapters.loader import load_input_adapters
from src.agent.agent import Agent
from src.core.messages import Message
from src.router.dispatch import DispatchOutputRouter


async def processing_worker(
    input_queue: asyncio.Queue[Message],
    output_queue: asyncio.Queue[Message | None],
    agent: Agent,
    stop_event: asyncio.Event,
) -> None:
    while True:
        if stop_event.is_set() and input_queue.empty():
            await output_queue.put(None)
            break

        try:
            message = await asyncio.wait_for(input_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            continue

        response = await agent.process(message)
        await output_queue.put(response)
        input_queue.task_done()


async def output_worker(
    output_queue: asyncio.Queue[Message | None],
    router: DispatchOutputRouter,
) -> None:
    while True:
        message = await output_queue.get()
        if message is None:
            output_queue.task_done()
            break

        await router.send(message)
        output_queue.task_done()


async def run() -> None:
    input_queue: asyncio.Queue[Message] = asyncio.Queue()
    output_queue: asyncio.Queue[Message | None] = asyncio.Queue()
    stop_event = asyncio.Event()

    adapters = load_input_adapters(input_queue=input_queue, stop_event=stop_event)
    if not adapters:
        raise RuntimeError("No input adapters found in src/adapters.")

    agent = Agent()
    router = DispatchOutputRouter()

    adapter_tasks = [asyncio.create_task(adapter.run()) for adapter in adapters]
    processing_task = asyncio.create_task(
        processing_worker(
            input_queue=input_queue,
            output_queue=output_queue,
            agent=agent,
            stop_event=stop_event,
        )
    )
    output_task = asyncio.create_task(
        output_worker(output_queue=output_queue, router=router)
    )

    await asyncio.gather(*adapter_tasks)
    stop_event.set()
    await processing_task
    await output_task


if __name__ == "__main__":
    asyncio.run(run())
