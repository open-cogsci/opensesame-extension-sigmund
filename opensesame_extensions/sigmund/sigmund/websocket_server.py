import asyncio
import websockets
import sys
import queue
from libopensesame.py3compat import *
from libopensesame.oslogging import oslogger

client_connected = False


async def queue_manager(websocket, path, to_main_queue, to_server_queue):
    """
    Concurrently read from the client and write to the client.
    Reading side: Puts messages into to_main_queue.
    Writing side: Polls messages from to_server_queue (non-blocking),
                  then sends them to the client.
    """

    async def read_task():
        to_main_queue.put("[DEBUG] Starting read_task")
        try:
            async for message in websocket:
                to_main_queue.put(f"[DEBUG] Message received from client")
                to_main_queue.put(message)
        except websockets.exceptions.ConnectionClosed:
            to_main_queue.put("[DEBUG] Client connection closed (read_task)")
        except Exception as e:
            to_main_queue.put(f"[DEBUG] Unexpected error in read_task: {e}")

    async def write_task():
        to_main_queue.put("[DEBUG] Starting write_task")
        try:
            while True:
                try:
                    msg_to_send = to_server_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.1)
                    continue
                to_main_queue.put(f"[DEBUG] Sending message to client")
                await websocket.send(msg_to_send)
        except websockets.exceptions.ConnectionClosed:
            to_main_queue.put("[DEBUG] Client connection closed (write_task)")
        except Exception as e:
            to_main_queue.put(f"[DEBUG] Unexpected error in write_task: {e}")            

    reader = asyncio.create_task(read_task())
    writer = asyncio.create_task(write_task())

    done, pending = await asyncio.wait(
        [reader, writer],
        return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()


async def server_handler(websocket, path, to_main_queue, to_server_queue):
    """
    Handles a new client connection. We only allow one client at a time. 
    If a client is already connected, refuse this new connection immediately.
    """
    global client_connected

    if client_connected:
        to_main_queue.put("[DEBUG] Refusing new connection; already connected")
        await websocket.close()
        return
    else:
        client_connected = True
        to_main_queue.put("[DEBUG] Client connected")
        to_main_queue.put("CLIENT_CONNECTED")

    try:
        await queue_manager(websocket, path, to_main_queue, to_server_queue)
    except Exception as e:
        to_main_queue.put(f"[DEBUG] An error occurred: {e}")
    finally:
        to_main_queue.put("[DEBUG] Client disconnected")
        client_connected = False
        to_main_queue.put("CLIENT_DISCONNECTED")


def start_server(to_main_queue, to_server_queue):
    """
    Start the WebSocket server to listen on localhost:8080.
    We wrap the server startup in a try/except so that a failure
    on websockets.serve() or loop.run_until_complete() is
    communicated back to the main process via to_main_queue.
    """
    try:
        loop = asyncio.get_event_loop()
        server = websockets.serve(
            lambda ws, path: server_handler(ws, path, to_main_queue, to_server_queue),
            "localhost",
            8080
        )
        loop.run_until_complete(server)
        loop.run_forever()
    except Exception as e:
        to_main_queue.put(f'FAILED_TO_START: {e}')
        sys.exit(1)
