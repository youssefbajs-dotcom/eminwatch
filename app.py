# app.py - EminWatch Server
import os
import time
from functools import wraps
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    session,
    url_for,
)

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
    "recording": False,
}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


# --- API ENDPOINTS FOR THE RASPBERRY PI ---


@app.route("/api/telemetry", methods=["POST"])
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


@app.route("/api/transcript", methods=["POST"])
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


@app.route("/api/toggle_transcription", methods=["POST"])
@login_required
def toggle_transcription():
    """Toggles the transcription recording state when button is pressed."""
    pi_state["recording"] = not pi_state["recording"]
    return jsonify({"recording": pi_state["recording"]})


# Route to serve custom static files
@app.route("/static/<path:filename>")
def custom_static(filename):
    return send_from_directory("static", filename)


# --- USER AUTHENTICATION ROUTES ---


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if (
            request.form.get("username") == "admin"
            and request.form.get("password") == "EminWatch2026"
        ):
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid credentials."

    return render_template_string(
        """
    <!DOCTYPE html>
    <html>
    <head>
        <title>EminWatch Login</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            html, body {
                margin: 0;
                padding: 0;
                width: 100%;
                font-family: sans-serif;
                color: #fff;
                background-color: #0f0f12;
            }

            .bg-scroll-wrapper {
                width: 100%;
                height: 250vh;
                background: url('/static/login_bg.jpg') no-repeat center top;
                background-size: cover;
                position: absolute;
                top: 0;
                left: 0;
                z-index: 1;
            }

            .login-box {
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                z-index: 999;
                background: rgba(0, 0, 0, 0.8);
                backdrop-filter: blur(8px);
                -webkit-backdrop-filter: blur(8px);
                padding: 35px;
                border-radius: 12px;
                width: 280px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.6);
                border: 1px solid rgba(255,255,255,0.15);
                text-align: center;
            }

            input {
                width: 100%;
                padding: 12px;
                margin-bottom: 12px;
                box-sizing: border-box;
                background: #222;
                border: 1px solid #444;
                color: white;
                border-radius: 6px;
                font-size: 16px;
            }

            button {
                width: 100%;
                padding: 12px;
                background: #007bff;
                color: #fff;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                cursor: pointer;
                font-size: 16px;
            }

            button:hover { background: #0056b3; }
            .error { color: #ff4757; font-size: 0.9em; margin-bottom: 10px; }

            audio {
                width: 100%;
                margin-top: 15px;
                height: 32px;
                border-radius: 6px;
            }
        </style>
    </head>
    <body>
        <div class="bg-scroll-wrapper"></div>

        <div class="login-box">
            <h2>EminWatch</h2>
            {% if error %}
                <div class="error">{{ error }}</div>
            {% endif %}
            <form method="post">
                <input type="text" name="username" placeholder="Username" required autocomplete="off"><br>
                <input type="password" name="password" placeholder="Password" required><br>
                <button type="submit">Log In</button>
            </form>

            <audio id="bg-audio" controls loop>
                <source src="/static/background_music.mp3" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
        </div>

        <script>
            document.addEventListener('click', function() {
                const audio = document.getElementById('bg-audio');
                if (audio.paused) {
                    audio.play();
                }
            }, { once: true });
        </script>
    </body>
    </html>
    """,
        error=error,
    )


@app.route("/logout")
def logout():
    """Logs out the current user and clears session."""
    session.pop("logged_in", None)
    return redirect(url_for("login"))


# --- MAIN DASHBOARD ROUTE ---


@app.route("/")
@login_required
def dashboard():
    is_online = pi_state["last_seen"] is not None and (
        time.time() - pi_state["last_seen"] < 15
    )

    return render_template_string(
        """
    <!DOCTYPE html>
    <html>
    <head>
        <title>EminWatch Live View</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; background: #0f0f12; color: #f0f0f0; margin: 0; padding: 20px; }
            .container { max-width: 900px; margin: 0 auto; position: relative; }
            
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
            
            /* Camera Container & Controls */
            .video-container { 
                position: relative; 
                width: 100%; 
                min-height: 300px; 
                background: #000; 
                border-radius: 6px; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                overflow: hidden;
            }

            .video-controls {
                display: flex;
                gap: 10px;
                margin-top: 10px;
            }

            .btn-action {
                background: #007bff;
                color: white;
                border: none;
                padding: 10px 18px;
                border-radius: 6px;
                font-size: 0.95em;
                font-weight: bold;
                cursor: pointer;
            }
            .btn-action.active { background: #dc3545; }

            .btn-snapshot {
                background: #28a745;
                color: white;
                border: none;
                padding: 10px 18px;
                border-radius: 6px;
                font-size: 0.95em;
                font-weight: bold;
                cursor: pointer;
            }
            .btn-snapshot:hover { background: #218838; }

            .btn-fullscreen {
                background: #6c5ce7;
                color: white;
                border: none;
                padding: 10px 18px;
                border-radius: 6px;
                font-size: 0.95em;
                font-weight: bold;
                cursor: pointer;
            }
            .btn-fullscreen:hover { background: #5b4bc4; }

            /* Overlay Stats Inside Fullscreen */
            .fs-overlay {
                display: none;
                position: absolute;
                top: 15px;
                left: 15px;
                background: rgba(0, 0, 0, 0.7);
                padding: 8px 12px;
                border-radius: 6px;
                font-family: monospace;
                font-size: 0.9em;
                color: #00ff88;
                z-index: 10;
                pointer-events: none;
            }

            .fs-btn-snapshot {
                display: none;
                position: absolute;
                bottom: 20px;
                right: 20px;
                z-index: 10;
            }

            /* Fullscreen Styling Adjustments */
            :fullscreen .video-container {
                width: 100vw;
                height: 100vh;
                border-radius: 0;
            }

            :fullscreen .fs-overlay,
            :fullscreen .fs-btn-snapshot {
                display: block;
            }

            :fullscreen #live-stream-img {
                max-width: 100%;
                max-height: 100%;
                object-fit: contain;
            }

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
                <div class="video-container" id="video-box">
                    <div class="fs-overlay" id="stats-overlay">
                        FPS: <span id="fps-counter">--</span> | Res: <span id="res-display">--x--</span>
                    </div>

                    {% if is_online and pi_state.camera_stream_url %}
                        <img id="live-stream-img" src="{{ pi_state.camera_stream_url }}" crossorigin="anonymous" style="width:100%; border-radius:6px;">
                    {% else %}
                        <p style="color:#777;">No active video stream available.</p>
                    {% endif %}

                    <button class="btn-snapshot fs-btn-snapshot" onclick="takeSnapshot()">📷 Take Photo</button>
                </div>

                {% if is_online and pi_state.camera_stream_url %}
                    <div class="video-controls">
                        <button class="btn-snapshot" onclick="takeSnapshot()">📷 Take Photo</button>
                        <button class="btn-fullscreen" onclick="toggleFullscreen()">⛶ Fullscreen Mode</button>
                    </div>
                {% endif %}
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

            // Save Camera Snapshot to PC
            function takeSnapshot() {
                const img = document.getElementById('live-stream-img');
                if (!img) return;

                const canvas = document.createElement('canvas');
                canvas.width = img.naturalWidth || img.width;
                canvas.height = img.naturalHeight || img.height;

                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

                const now = new Date();
                const timestamp = now.toISOString().replace(/[:T]/g, '-').split('.')[0];
                const filename = `EminWatch_${timestamp}.jpg`;

                const link = document.createElement('a');
                link.download = filename;
                link.href = canvas.toDataURL('image/jpeg', 0.95);
                link.click();
            }

            // Toggle Fullscreen Mode
            function toggleFullscreen() {
                const box = document.getElementById('video-box');
                if (!document.fullscreenElement) {
                    if (box.requestFullscreen) {
                        box.requestFullscreen();
                    } else if (box.webkitRequestFullscreen) {
                        box.webkitRequestFullscreen();
                    }
                } else {
                    if (document.exitFullscreen) {
                        document.exitFullscreen();
                    }
                }
            }

            // FPS & Resolution Calculator
            let frameCount = 0;
            let lastTime = performance.now();
            const imgEl = document.getElementById('live-stream-img');

            if (imgEl) {
                imgEl.onload = function() {
                    frameCount++;
                    const now = performance.now();

                    // Display resolution quality
                    if (imgEl.naturalWidth && imgEl.naturalHeight) {
                        document.getElementById('res-display').innerText = 
                            `${imgEl.naturalWidth}x${imgEl.naturalHeight}`;
                    }

                    // Calculate real-time FPS
                    if (now - lastTime >= 1000) {
                        const fps = Math.round((frameCount * 1000) / (now - lastTime));
                        document.getElementById('fps-counter').innerText = fps;
                        frameCount = 0;
                        lastTime = now;
                    }
                };
            }
        </script>
    </body>
    </html>
    """,
        is_online=is_online,
        pi_state=pi_state,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
