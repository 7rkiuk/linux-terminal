import docker, os, uuid
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from openai import OpenAI

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
client = docker.from_env()
ai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# المسار الذي ستُخزن فيه ملفات المستخدمين بشكل دائم
STORAGE_PATH = "/app/user_data"
os.makedirs(STORAGE_PATH, exist_ok=True)

user_sessions = {}

@app.route('/')
def index(): return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    user_id = str(uuid.uuid4())
    user_dir = os.path.join(STORAGE_PATH, user_id)
    os.makedirs(user_dir, exist_ok=True)
    
    # ربط المجلد المحلي بحاوية اللينكس
    container = client.containers.run(
        "alpine:latest", "sh", detach=True, tty=True,
        volumes={user_dir: {'bind': '/home/user', 'mode': 'rw'}},
        working_dir="/home/user"
    )
    user_sessions[request.sid] = container

@socketio.on('cmd')
def handle_cmd(data):
    container = user_sessions.get(request.sid)
    if not container: return
    res = container.exec_run(data['command'])
    out = res.output.decode()
    if res.exit_code != 0:
        out += "\n\n[AI Debug]: " + ai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": f"Fix error: {out}"}]
        ).choices[0].message.content
    emit('output', {'text': out})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
