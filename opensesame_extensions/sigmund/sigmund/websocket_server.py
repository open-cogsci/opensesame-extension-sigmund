import asyncio
import websockets
import sys
from libopensesame.py3compat import *
from libopensesame.oslogging import oslogger

client_connected = False


# Because queue.get() is blocking, we’ll call it in a thread executor via
# run_in_executor() so it doesn’t block our event loop.
def blocking_queue_get(q):
    return q.get()


async def echo(websocket, path, to_main_queue, to_server_queue):
    """
    Concurrently read from the client and write to the client.
    Reading side: Puts messages into to_main_queue.
    Writing side: Pulls messages from to_server_queue (blocking),
                  then sends them to the client.
    """

    async def read_task():
        # Continuously read messages from the client
        try:
            async for message in websocket:
                oslogger.debug(f"WebSocket server received message: {message}")
                to_main_queue.put(message)
        except websockets.exceptions.ConnectionClosed:
            oslogger.debug("Client connection closed (read_task)")

    async def write_task():
        # Continuously check if we have messages to send from the server queue
        try:
            while True:
                # Offload the blocking queue.get() call
                msg_to_send = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: blocking_queue_get(to_server_queue)
                )
                oslogger.debug(f"Sending to client: {msg_to_send}")
                await websocket.send(msg_to_send)
        except websockets.exceptions.ConnectionClosed:
            oslogger.debug("Client connection closed (write_task)")

    # Run both tasks until one of them finishes
    reader = asyncio.create_task(read_task())
    writer = asyncio.create_task(write_task())

    done, pending = await asyncio.wait(
        [reader, writer],
        return_when=asyncio.FIRST_COMPLETED
    )

    # Cancel whatever didn’t finish first
    for task in pending:
        task.cancel()


async def server_handler(websocket, path, to_main_queue, to_server_queue):
    """
    Handles a new client connection. We only allow one client at a time. 
    If a client is already connected, refuse this new connection immediately.
    """
    global client_connected

    # Check if a client is already connected
    if client_connected:
        oslogger.debug("Refusing new connection, because a client is already connected.")
        # Close this new websocket immediately
        await websocket.close()
        return
    else:
        # Accept this connection
        client_connected = True
        to_main_queue.put("CLIENT_CONNECTED")

    try:
        await echo(websocket, path, to_main_queue, to_server_queue)
    finally:
        client_connected = False
        to_main_queue.put("CLIENT_DISCONNECTED")


def start_server(to_main_queue, to_server_queue):
    """
    Start the WebSocket server to listen on localhost:8080.
    We wrap the server startup in a try/except so that a failure
    on "websockets.serve()" or loop.run_until_complete() is
    communicated back to the main process via to_main_queue.
    """
    oslogger.start('sigmund')
    try:
        loop = asyncio.get_event_loop()
        server = websockets.serve(
            lambda ws, path: server_handler(ws, path, to_main_queue,
                                            to_server_queue),
            "localhost",
            8080
        )
        loop.run_until_complete(server)
        loop.run_forever()

    except Exception as e:
        # Notify the main process that the server failed to start
        to_main_queue.put('FAILED_TO_START')
        sys.exit(1)
