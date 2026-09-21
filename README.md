# StudyGuard

StudyGuard watches a study session through a webcam and decides whether the person in frame is actually studying. If they aren't, it blocks distracting sites over DNS, speaks up through a voice agent, and makes a Reachy Mini react, while a parent dashboard shows what is going on. An Isaac Sim copy of the room runs the same pipeline without a real camera.

## Features

| Feature | What it does |
|---------|-------------|
| Vision monitoring | Real-time camera analysis, streamed to the dashboard |
| Voice agent | Speech in, speech out |
| Website blocking | DNS-level blocks; AI rules on unlock requests |
| Robot companion | Reachy Mini reacts with head and antenna moves |
| Parent dashboard | Live view, site management, logs, system health |
| Activity tracking | Sessions and events in SQLite, plus daily stats |
| Omniverse simulation | Isaac Sim synthetic camera for testing before real deployment |

## How it fits together

A Jetson Orin Nano runs the FastAPI backend, DNS controls, state tracking and local AI. A Reachy Mini gives the physical reaction. Omniverse and Isaac Sim make the study-room scene, the Replicator data and the synthetic camera feed. The dashboard gives parents visibility, moderation and activity review.

Backend is FastAPI, SQLAlchemy, OpenAI API, OpenCV and PyAudio. Frontend is vanilla JS with HTML/CSS. DNS is dnsmasq, the robot uses the `reachy_mini` SDK, storage is SQLite.

## Omniverse and Isaac Sim

Isaac Sim holds a virtual copy of the study room: desk, chair, laptop, book, notebook, phone, lamp, a camera, a robot avatar and a few student identities. Replicator renders labelled frames from it, so monitoring, identity recognition, attention detection, robot feedback and blocking can all be tested without a live webcam.

Scenarios cover Jason studying, on his phone or distracted; Nayab detected; a stranger walking in; bad lighting; a messy desk; an occluded phone; side camera angles; and more than one person in frame. Labels:

```text
identity = Jason / Nayab / unknown
state = studying / phone_use / distracted
objects = person / phone / book / laptop / notebook
```

Press Run NVIDIA Omniverse Simulation Test on the dashboard and those frames arrive through the simulation camera path. Everything downstream behaves as if it were live: dashboard logs, robot reactions, identity detection, DNS blocking.

## Layout

```text
backend/
  main.py             FastAPI server and startup
  vision.py           camera monitoring and classification
  voice_loop.py       voice agent and speech processing
  argue.py            website access requests
  reachy_control.py   robot gestures
  database.py         models and DB setup
  sim_camera.py       Omniverse synthetic frame input
frontend/             index.html, dashboard.js, style.css
simulation/           Omniverse scenes, scripts, frames, labels
robot_photo_demo.py       single-frame Reachy capture
robot_video_360_demo.py   Reachy 360-degree video
run.sh                    startup script
```

## Getting started

You need Python 3.10+, an OpenAI API key, a camera and a mic. Reachy Mini, dnsmasq and Omniverse / Isaac Sim are optional.

```bash
git clone https://github.com/Nayab-23/SeedHackathon.git
cd SeedHackathon
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Put `OPENAI_API_KEY=your-key-here` in a `.env`. Everything else is optional:

```env
DATABASE_URL=sqlite:///./studyguard.db
DNS_LOG_PATH=./dnsmasq.log
CAMERA_INDEX=0
VISION_INTERVAL_SECONDS=10
REACHY_HOST=localhost
REACHY_PORT=8080
STUDYGUARD_AUDIO_SINK=default
STUDYGUARD_AUDIO_SOURCE=default
```

Then run it and open http://localhost:8000:

```bash
./run.sh   # or: uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## Reachy camera demos

```bash
source .reachy-mini-venv/bin/activate
python robot_photo_demo.py --host reachy-mini.local         # one photo
python robot_video_360_demo.py --duration 10 --return-home  # 10s video, full turn
```

Both save to `captures/` by default.

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check |
| `GET /api/status` | System status |
| `GET /api/stats/today` | Today's study stats |
| `GET /api/camera/stream` | Live MJPEG stream |
| `GET /api/events` | Activity log |
| `GET /api/logs/dns` | DNS query logs |
| `GET` / `POST /api/blocklist`, `DELETE /api/blocklist/{domain}` | List, add and remove blocked domains |
| `POST /api/argue` | Submit access argument |
| `POST /api/voice/listening` | Toggle microphone |
| `GET /api/voice/conversation` | Conversation transcript |

## What's next

MCP support, so Codex and Claude can generate Omniverse scenarios directly for faster iteration and automated simulation runs.
