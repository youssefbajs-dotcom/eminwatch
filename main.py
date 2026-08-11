# app.py - EminWatch Server
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from functools import wraps
import time

app = Flask(__name__)
app.secret_key = "eminwatch_secure_secret_key_change_me"

# Secret token so only YOUR Pi can push data to your website
API_KEY = "eminwatch_pi_token_123"

# Real-time state store (Initially empty / disconnected)
pi_state = {
    "last_seen": None,
    "battery_percentage": None,
    "battery_voltage": None,
    "camera_stream_url": None,
    "transcripts": []
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- API ENDPOINTS FOR THE RASPBERRY PI ---

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    """Receives real battery and status updates from the Pi."""
    data = request.json
    if request.headers.get("X-API-KEY") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    pi_state["last_seen"] = time.time()
    pi_state["battery_percentage"] = data.get("battery_pct")
    pi_state["battery_voltage"] = data.get("battery_volts")
    pi_state["camera_stream_url"] = data.get("stream_url")
    return jsonify({"status": "success"})

@app.route('/api/transcript', methods=['POST'])
def receive_transcript():
    """Receives live transcribed speech from the Pi's microphone."""
    data = request.json
    if request.headers.get("X-API-KEY") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    text = data.get("text")
    if text:
        timestamp = time.strftime("%H:%M:%S")
        pi_state["transcripts"].insert(0, f"[{timestamp}] {text}")
        if len(pi_state["transcripts"]) > 20:
            pi_state["transcripts"].pop()
    return jsonify({"status": "success"})

# --- USER FRONTEND ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        # Default password setup
        if request.form.get('username') == 'admin' and request.form.get('password') == 'EminWatch2026':
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid credentials.'
    
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>EminWatch Login</title><meta name="viewport" content="width=device-width, initial-scale=1"></head>
    <body style="background:#111; color:#fff; font-family:sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; margin:0;">
        <form method="post" style="background:#222; padding:30px; border-radius:8px; width:280px;">
            <h2>EminWatch</h2>
            <input type="text" name="username" placeholder="Username" required style="width:100%; padding:8px; margin-bottom:10px;"><br>
            <input type="password" name="password" placeholder="Password" required style="width:100%; padding:8px; margin-bottom:15px;"><br>
            <button type="submit" style="width:100%; padding:10px; background:#007bff; color:#fff; border:none; border-radius:4px;">Log In</button>
        </form>
    </body>
    </html>
    '''

@app.route('/')
@login_required
def dashboard():
    # Determine if Pi is actively sending data (within 15 seconds)
    is_online = pi_state["last_seen"] is not None and (time.time() - pi_state["last_seen"] < 15)
    
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>EminWatch Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta http-equiv="refresh" content="5">
        <style>
            body { font-family: Arial, sans-serif; background: #0f0f12; color: #f0f0f0; margin: 0; padding: 20px; }
            .container { max-width: 900px; margin: 0 auto; }
            .card { background: #1a1a24; padding: 20px; margin-bottom: 20px; border-radius: 10px; border: 1px solid #2d2d3f; }
            .status-online { color: #00ff88; font-weight: bold; }
            .status-offline { color: #ff4757; font-weight: bold; }
            .video-container { width: 100%; min-height: 300px; background: #000; border-radius: 6px; display: flex; align-items: center; justify-content: center; }
            ul { list-style: none; padding: 0; max-height: 200px; overflow-y: auto; }
            li { background: #252538; padding: 8px 12px; margin-bottom: 6px; border-radius: 4px; font-family: monospace; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <h1>EminWatch Live Dashboard</h1>
                <p>Status: 
                    {% if is_online %}
                        <span class="status-online">● PI ONLINE</span>
                    {% else %}
                        <span class="status-offline">○ PI DISCONNECTED / WAITING FOR HARDWARE</span>
                    {% endif %}
                </p>
            </div>

            <div class="card">
                <h3>Live Camera Feed</h3>
                <div class="video-container">
                    {% if is_online and pi_state.camera_stream_url %}
                        <img src="{{ pi_state.camera_stream_url }}" style="width:100%; border-radius:6px;">
                    {% else %}
                        <p style="color:#777;">No active video stream available.</p>
                    {% endif %}
                </div>
            </div>

            <div class="card">
                <h3>Battery & Hardware Telemetry</h3>
                <p>Battery Percentage: <strong>{{ pi_state.battery_percentage if is_online and pi_state.battery_percentage is not none else 'N/A' }}%</strong></p>
                <p>Battery Voltage: <strong>{{ pi_state.battery_voltage if is_online and pi_state.battery_voltage is not none else 'N/A' }} V</strong></p>
            </div>

            <div class="card">
                <h3>Live Microphone Transcriptions</h3>
                <ul>
                    {% for item in pi_state.transcripts %}
                        <li>{{ item }}</li>
                    {% else %}
                        <li style="color:#777;">No transcriptions received yet.</li>
                    {% endfor %}
                </ul>
            </div>
        </div>
    </body>
    </html>
    ''', is_online=is_online, pi_state=pi_state)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
