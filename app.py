import os
import uuid
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from openai import OpenAI
import docker

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# محاولة الاتصال بـ Docker بلطف لكي لا يتوقف التطبيق إذا لم يكن موجوداً
try:
  client = docker.from_env()
except Exception as e:
  print(f"[Warning] Docker is not available: {e}")
  client = None

# إعداد عميل DeepSeek
ai_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com"
)

STORAGE_PATH = "/app/user_data"
os.makedirs(STORAGE_PATH, exist_ok=True)

user_sessions = {}


@app.route("/")
def index():
  return render_template("index.html")


@socketio.on("connect")
def handle_connect():
  if not client:
    return
  user_id = str(uuid.uuid4())
  user_dir = os.path.join(STORAGE_PATH, user_id)
  os.makedirs(user_dir, exist_ok=True)

  container = client.containers.run(
      "alpine:latest",
      "sh",
      detach=True,
      tty=True,
      volumes={user_dir: {"bind": "/home/user", "mode": "rw"}},
      working_dir="/home/user",
  )
  user_sessions[request.sid] = container


@socketio.on("cmd")
def handle_cmd(data):
  container = user_sessions.get(request.sid)
  if not container:
    emit(
        "output",
        {
            "text": (
                "Error: Docker container not active on this cloud instance."
            )
        },
    )
    return
  res = container.exec_run(data["command"])
  out = res.output.decode()

  if res.exit_code != 0:
    response = ai_client.chat.completions.create(
        model="deepseek-flash",
        messages=[{"role": "user", "content": f"Fix error: {out}"}],
    )
    out += "\n\n[AI Debug]: " + response.choices[0].message.content

  emit("output", {"text": out})


if __name__ == "__main__":
  socketio.run(app, host="0.0.0.0", port=5000)
