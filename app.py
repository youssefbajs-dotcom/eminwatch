# app.py - EminWatch Server
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for, send_from_directory
from functools import wraps
import time
import os

app = Flask(__name__)
app.secret_key = "eminwatch_secure_secret_key_change_me"

# Secret token so only YOUR Pi can push data to your website
API_KEY = "eminwatch_pi_token_123"

# Real-time state store
pi_state = {
    "last_seen": None,
    "battery_percentage": None,
    "battery_voltage": None,
    "camera_stream_url": None,
    "transcripts": [],
    "recording": False
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
    return jsonify({"status": "success", "recording": pi_state["recording"]})

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

@app.route('/api/toggle_transcription', methods=['POST'])
@login_required
def toggle_transcription():
    """Toggles the transcription recording state when button is pressed."""
    pi_state["recording"] = not pi_state["recording"]
    return jsonify({"recording": pi_state["recording"]})

# Route to serve custom static files (like login_bg.jpg)
@app.route('/static/<path:filename>')
def custom_static(filename):
    return send_from_directory('static', filename)

# --- USER AUTHENTICATION ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('username') == 'admin' and request.form.get('password') == 'EminWatch2026':
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid credentials.'
    
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>EminWatch Login</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                background: url('/static/login_bg.jpg') no-repeat center center fixed;
                background-size: cover;
                color: #fff;
                font-family: sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }
            .login-box {
                background: rgba(0, 0, 0, 0.75);
                backdrop-filter: blur(5px);
                padding: 35px;
                border-radius: 12px;
                width: 300px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.5);
                border: 1px solid rgba(255,255,255,0.1);
            }
            input {
                width: 100%;
                padding: 10px;
                margin-bottom: 12px;
                box-sizing: border-box;
                background: #222;
                border: 1px solid #444;
                color: white;
                border-radius: 4px;
            }
            button {
                width: 100%;
                padding: 12px;
                background: #007bff;
                color: #fff;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                cursor: pointer;
            }
            button:hover { background: #0056b3; }
            .error { color: #ff4757; font-size: 0.9em; margin-bottom: 10px; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>EminWatch</h2>
            ''' + (f'<div class="error">{error}</div>' if error else '') + '''
            <form method="post">
                <input type="text" name="username" placeholder="Username" required><br>
                <input type="password" name="password" placeholder="Password" required><br>
                <button type="submit">Log In</button>
            </form>
        </div>
    </body>
    </html>
    '''

@app.route('/logout')
def logout():
    """Logs out the current user and clears session."""
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# --- MAIN DASHBOARD ROUTE ---

@app.route('/')
@login_required
def dashboard():
    is_online = pi_state["last_seen"] is not None and (time.time() - pi_state["last_seen"] < 15)
    
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>EminWatch Live View</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; background: #0f0f12; color: #f0f0f0; margin: 0; padding: 20px; }
            .container { max-width: 900px; margin: 0 auto; position: relative; }
            
            /* Header Control Controls (Timer & Logout) */
            .header-controls {
                position: absolute;
                top: 20px;
                right: 20px;
                display: flex;
                gap: 10px;
                align-items: center;
            }

            .timer-badge {
                background: #1a1a24;
                border: 1px solid #00ff88;
                color: #00ff88;
                padding: 8px 14px;
                border-radius: 6px;
                font-family: monospace;
                font-size: 1.1em;
                font-weight: bold;
            }

            .btn-logout {
                background: #ff4757;
                color: white;
                text-decoration: none;
                padding: 8px 14px;
                border-radius: 6px;
                font-size: 0.9em;
                font-weight: bold;
            }
            .btn-logout:hover { background: #ff6b81; }

            .card { background: #1a1a24; padding: 20px; margin-bottom: 20px; border-radius: 10px; border: 1px solid #2d2d3f; }
            .status-online { color: #00ff88; font-weight: bold; }
            .status-offline { color: #ff4757; font-weight: bold; }
            .video-container { width: 100%; min-height: 300px; background: #000; border-radius: 6px; display: flex; align-items: center; justify-content: center; }
            
            /* Action Button */
            .btn-action {
                background: #007bff;
                color: white;
                border: none;
                padding: 10px 18px;
                border-radius: 6px;
                font-size: 0.95em;
                font-weight: bold;
                cursor: pointer;
                margin-top: 10px;
            }
            .btn-action.active { background: #dc3545; }
            
            ul { list-style: none; padding: 0; max-height: 200px; overflow-y: auto; }
            li { background: #252538; padding: 8px 12px; margin-bottom: 6px; border-radius: 4px; font-family: monospace; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-controls">
                <div class="timer-badge" id="session-timer">00:00:00</div>
                <a href="/logout" class="btn-logout">Log Out</a>
            </div>

            <div class="card">
                <h1>EminWatch Live View</h1>
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
                <button id="transcribe-btn" class="btn-action {{ 'active' if pi_state.recording else '' }}" onclick="toggleTranscription()">
                    {{ 'Stop Transcription' if pi_state.recording else 'Start Transcription' }}
                </button>
                <ul id="transcript-list">
                    {% for item in pi_state.transcripts %}
                        <li>{{ item }}</li>
                    {% else %}
                        <li style="color:#777;">No transcriptions received yet.</li>
                    {% endfor %}
                </ul>
            </div>
        </div>

        <script>
            // Live Session Timer
            let secondsElapsed = 0;
            function updateTimer() {
                secondsElapsed++;
                let hrs = Math.floor(secondsElapsed / 3600);
                let mins = Math.floor((secondsElapsed % 3600) / 60);
                let secs = secondsElapsed % 60;
                
                let formatted = 
                    String(hrs).padStart(2, '0') + ':' +
                    String(mins).padStart(2, '0') + ':' +
                    String(secs).padStart(2, '0');
                
                document.getElementById('session-timer').innerText = formatted;
            }
            setInterval(updateTimer, 1000);

            // Toggle Transcription Request
            function toggleTranscription() {
                fetch('/api/toggle_transcription', { method: 'POST' })
                    .then(res => res.json())
                    .then(data => {
                        const btn = document.getElementById('transcribe-btn');
                        if (data.recording) {
                            btn.innerText = 'Stop Transcription';
                            btn.classList.add('active');
                        } else {
                            btn.innerText = 'Start Transcription';
                            btn.classList.remove('active');
                        }
                    });
            }
        </script>
    </body>
    </html>
    ''', is_online=is_online, pi_state=pi_state)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
