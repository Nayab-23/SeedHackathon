#!/bin/bash
echo "Starting StudyGuard..."
set -a
source /home/seeed/studyguard/.env
set +a

cd /home/seeed/studyguard
source venv/bin/activate

pkill -f "uvicorn backend.main:app --host 0.0.0.0 --port 8000" >/dev/null 2>&1 || true

if command -v pactl >/dev/null 2>&1; then
  pactl set-default-sink "${STUDYGUARD_AUDIO_SINK}" || true
  pactl set-default-source "${STUDYGUARD_AUDIO_SOURCE}" || true
  pactl set-sink-volume "${STUDYGUARD_AUDIO_SINK}" "${STUDYGUARD_AUDIO_SINK_VOLUME:-150%}" || true
  pactl set-source-volume "${STUDYGUARD_AUDIO_SOURCE}" 100% || true
fi

if command -v amixer >/dev/null 2>&1; then
  amixer -c 0 sset "PCM",0 100%,100% unmute || true
  amixer -c 0 sset "PCM",1 100% unmute || true
fi

echo "Server starting at http://10.251.75.32:8000"
uvicorn backend.main:app --host 0.0.0.0 --port 8000
