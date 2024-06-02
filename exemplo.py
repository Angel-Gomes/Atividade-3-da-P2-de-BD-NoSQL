from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import aioredis
import json
import asyncio

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

redis = aioredis.from_url("redis://localhost", decode_responses=True)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = {"client_id": client_id, "message": data}
            await redis.publish("chat", json.dumps(message))
            await manager.send_personal_message(f"Você escreveu: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await redis.publish("chat", json.dumps({"client_id": client_id, "message": "saiu do chat"}))

async def chat_listener():
    pubsub = redis.pubsub()
    await pubsub.subscribe("chat")
    async for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            await manager.broadcast(f"Cliente #{data['client_id']} disse: {data['message']}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(chat_listener())
