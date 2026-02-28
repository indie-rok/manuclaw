import asyncio
import websockets


async def handler(websocket):
    """Handle incoming WebSocket connections."""
    print("[gateway] client connected")
    try:
        async for message in websocket:
            print(f"[gateway] received: {message}")
            await asyncio.sleep(0.5)
            response = f"I'm manuclaw, your AI assistant. I received: {message}"
            await websocket.send(response)
    except websockets.exceptions.ConnectionClosedOK:
        print("[gateway] client disconnected")
    except websockets.exceptions.ConnectionClosedError:
        print("[gateway] client disconnected")


async def main():
    """Start the WebSocket server."""
    async with websockets.serve(handler, "localhost", 8765):
        print("[gateway] server started on ws://localhost:8765")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())