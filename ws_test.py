import asyncio
import websockets

async def test_ws():
    uri = "ws://localhost:8080/ws/patient/91-1234-5678-9012"
    async with websockets.connect(uri) as websocket:
        print("Connected!")
        await asyncio.sleep(5)
        print("Still connected!")

asyncio.run(test_ws())
