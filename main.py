from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import aioredis
import json

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

redis = aioredis.from_url("redis://localhost", decode_responses=True)

html = """
<!DOCTYPE html>
<html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Chat</title>
        <link rel="stylesheet" href="/static/styles.css">
    </head>
    <body>
        <div class="chat-container">
            <h1> Chat para Fofocas </h1>
            <h2>ID do Usuário: <span id="ws-id"></span></h2>
            <form id="messageForm">
                <input type="text" id="messageText" autocomplete="off" aria-label="Digite sua mensagem">
                <button type="submit">Enviar</button>
            </form>
            <ul id='messages'></ul>
            <div id="feedback" role="alert" aria-live="assertive" class="feedback"></div>
            <template id="messageTemplate">
                <li></li>
            </template>
        </div>
        <script>
            document.addEventListener("DOMContentLoaded", function() {
                var client_id = Date.now();
                var ws = new WebSocket(`ws://localhost:8000/ws/${client_id}`);
                var wsIdElement = document.getElementById("ws-id");
                var messageForm = document.getElementById("messageForm");
                var messageText = document.getElementById("messageText");
                var messagesList = document.getElementById("messages");
                var feedback = document.getElementById("feedback");
                var messageTemplate = document.getElementById("messageTemplate");

                wsIdElement.textContent = client_id;

                ws.onmessage = function(event) {
                    var message = messageTemplate.content.cloneNode(true).querySelector("li");
                    message.textContent = event.data;
                    messagesList.appendChild(message);
                };

                messageForm.addEventListener("submit", function(event) {
                    event.preventDefault();
                    var message = messageText.value.trim();
                    if (message !== "") {
                        ws.send(message);
                        messageText.value = "";
                        showFeedback("Mensagem enviada com sucesso.", "success");
                    } else {
                        showFeedback("Por favor, digite uma mensagem.", "error");
                    }
                });

                ws.onerror = function(event) {
                    console.error("WebSocket error:", event);
                    showFeedback("Erro no WebSocket. Tente novamente mais tarde.", "error");
                };

                ws.onclose = function(event) {
                    console.log("WebSocket closed:", event);
                    showFeedback("Conexão do WebSocket fechada.", "warning");
                };

                function showFeedback(message, type) {
                    feedback.textContent = message;
                    feedback.style.display = "block";
                    feedback.className = `feedback ${type}`;
                    setTimeout(function() {
                        feedback.style.display = "none";
                    }, 3000);
                }
            });
        </script>
    </body>
</html>
"""

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
async def get():
    return HTMLResponse(html)

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
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(chat_listener())
    