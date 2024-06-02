from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

html = """
<!DOCTYPE html>
<html lang="pt-BR">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Chat</title>
        <style>
        /* Adicione estilos CSS aqui */
    </style>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <h2>Your ID: <span id="ws-id"></span></h2>
        <form id="messageForm">
            <input type="text" id="messageText" autocomplete="off" aria-label="Type your message">
            <button type="submit">Send</button>
        </form>
        <ul id='messages'></ul>
        <div id="feedback" role="alert" aria-live="assertive" style="display: none;"></div>
        
        <template id="messageTemplate">
            <li></li>
        </template>
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
                    var message = document.createElement("li");
                    message.textContent = event.data;
                    messagesList.appendChild(message);
                };
    
                messageForm.addEventListener("submit", function(event) {
                    event.preventDefault();
                    var message = messageText.value.trim();
                    if (message !== "") {
                        ws.send(message);
                        messageText.value = "";
                        showFeedback("Message sent successfully.", "success");
                    } else {
                        showFeedback("Please enter a message.", "error");
                    }
                });
    
                ws.onerror = function(event) {
                    console.error("WebSocket error:", event);
                    showFeedback("WebSocket error. Please try again later.", "error");
                };
    
                ws.onclose = function(event) {
                    console.log("WebSocket closed:", event);
                    showFeedback("WebSocket connection closed.", "warning");
                };
                
                function showFeedback(message, type) {
                    feedback.textContent = message;
                    feedback.style.display = "block";
                    feedback.className = type;
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
            await manager.send_personal_message(f"You wrote: {data}", websocket)
            await manager.broadcast(f"Client #{client_id} says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client #{client_id} left the chat")
