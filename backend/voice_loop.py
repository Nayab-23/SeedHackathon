import asyncio
import os
import re
import struct
import subprocess
import tempfile
import threading
import time
import wave

import pyaudio
from dotenv import load_dotenv
from openai import OpenAI

from backend.argue import get_blocked_domains, normalize_domain, update_dns_allowlist

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Audio settings
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
SILENCE_THRESHOLD = 600
SILENCE_DURATION = 1.8
MAX_RECORD_SECONDS = 15

# Global refs set from main.py
state_manager_ref = None
reachy_ref = None
debug_callback_ref = None
is_speaking = False

# Conversation memory — persists entire session
conversation_history = []
_pending_domain = ""

_voice_thread = None
_status_lock = threading.Lock()
_voice_state = "starting"
_last_heard = ""
_last_error = ""
_listening_enabled = False
_armed_until = 0.0
_default_sink = os.getenv(
    "STUDYGUARD_AUDIO_SINK",
    "alsa_output.usb-Pollen_Robotics_Reachy_Mini_Audio_100025004260200255-00.analog-stereo",
)
_default_source = os.getenv(
    "STUDYGUARD_AUDIO_SOURCE",
    "alsa_input.usb-Pollen_Robotics_Reachy_Mini_Audio_100025004260200255-00.analog-stereo",
)
_preferred_input_name = os.getenv("STUDYGUARD_AUDIO_INPUT_NAME", "Reachy Mini Audio")
_alsa_playback_device = os.getenv("STUDYGUARD_AUDIO_ALSA_DEVICE", "plughw:0,0")
_pulse_playback_enabled = os.getenv("STUDYGUARD_AUDIO_USE_PULSE", "1").strip().lower() not in {"0", "false", "no"}
DEFAULT_LISTEN_WINDOW_SECONDS = int(os.getenv("STUDYGUARD_LISTEN_WINDOW_SECONDS", "20"))
FOLLOWUP_GRACE_SECONDS = int(os.getenv("STUDYGUARD_FOLLOWUP_GRACE_SECONDS", "8"))
KNOWN_DOMAIN_ALIASES = {
    "youtube": "youtube.com",
    "you tube": "youtube.com",
    "youtube.com": "youtube.com",
    "instagram": "instagram.com",
    "instagram.com": "instagram.com",
    "tiktok": "tiktok.com",
    "tik tok": "tiktok.com",
    "tiktok.com": "tiktok.com",
    "twitter": "twitter.com",
    "twitter.com": "twitter.com",
    "x.com": "twitter.com",
    "reddit": "reddit.com",
    "reddit.com": "reddit.com",
    "google": "google.com",
    "google.com": "google.com",
    "github": "github.com",
    "github.com": "github.com",
}
ACTION_GRANT_RE = re.compile(r"(?i)ACTION[_\s-]*GRANT\s*:\s*([a-z0-9.\-]+)\s*:\s*(\d{1,3})")
ACTION_DENY_RE = re.compile(r"(?i)ACTION[_\s-]*DENY\s*:\s*([a-z0-9.\-]+)")

SYSTEM_PROMPT = """
You are StudyGuard, the voice of a Reachy Mini study companion.
You help a child stay focused, but you should also feel natural to talk to.
You sound like a sharp, caring older sibling: warm, direct, and firm when needed.

YOUR STYLE:
- Speak in short natural sentences, usually 1 to 3.
- Never say you are an AI.
- Hold a real back-and-forth conversation.
- Answer normal questions briefly, then steer back toward studying when it makes sense.
- If the child says your name, greets you, or calls for you, answer naturally.

YOUR CONTEXT:
- You can monitor whether the child is studying or distracted.
- You can block and unblock websites.
- You know how long they have studied today.

RULES FOR WEBSITE REQUESTS:
- If they ask to use a blocked site, ask why first unless they already gave a reason.
- Never unblock immediately on a vague request.
- Grant access for specific educational reasons.
- Deny access for vague, entertainment, or off-topic reasons.
- When you grant, give a clear time limit and a warning to stay on task.

ACTION FORMAT:
- Put actions only on the final line.
- Grant format: ACTION_GRANT:domain.com:30
- Deny format: ACTION_DENY:domain.com
- If no action is needed, do not output an action line.

Never say the action line out loud. Only the spoken reply goes before it.

GOOD EXAMPLES:
Child: "Can I use YouTube?"
You: "Maybe. What exactly do you need it for?"

Child: "I need a Calculus 3 tutorial for homework."
You: "Alright, that's a fair reason. You've got 30 minutes, so stay on topic."
ACTION_GRANT:youtube.com:30

Child: "Can I use Instagram?"
You: "No. Instagram is not helping you study right now."
ACTION_DENY:instagram.com

Child: "StudyGuard, are you there?"
You: "Yeah, I'm here. What do you need?"
"""


def _push_debug(kind: str, text: str) -> None:
    if debug_callback_ref:
        try:
            debug_callback_ref(kind, text)
        except Exception:
            pass


def _set_state(state: str) -> None:
    global _voice_state
    with _status_lock:
        _voice_state = state


def _set_last_heard(text: str) -> None:
    global _last_heard
    with _status_lock:
        _last_heard = text


def _set_last_error(text: str) -> None:
    global _last_error
    with _status_lock:
        _last_error = text


def _arm_listening(duration_seconds: int | None = None) -> None:
    global _listening_enabled, _armed_until, _voice_state
    seconds = max(1, int(duration_seconds or DEFAULT_LISTEN_WINDOW_SECONDS))
    with _status_lock:
        _listening_enabled = True
        _armed_until = time.time() + seconds
        if not is_speaking:
            _voice_state = "listening"
    _push_debug("voice_arm", f"Mic armed for {seconds} seconds")


def _disarm_listening(reason: str = "manual") -> None:
    global _listening_enabled, _armed_until, _pending_domain, _voice_state
    with _status_lock:
        _listening_enabled = False
        _armed_until = 0.0
        if not is_speaking:
            _voice_state = "sleeping"
    _pending_domain = ""
    _push_debug("voice_mute", f"Mic muted ({reason})")


def set_listening_enabled(enabled: bool, duration_seconds: int | None = None) -> dict:
    if enabled:
        _arm_listening(duration_seconds)
    else:
        _disarm_listening("manual")
    return get_voice_status()


def _should_listen() -> bool:
    with _status_lock:
        enabled = _listening_enabled
        armed_until = _armed_until
    if not enabled:
        return False
    if armed_until and time.time() > armed_until:
        _disarm_listening("timeout")
        return False
    return True


def _detect_domain_from_text(text: str) -> str:
    raw = (text or "").strip().lower()
    if not raw:
        return ""

    blocked = set(get_blocked_domains())

    for alias, domain in KNOWN_DOMAIN_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", raw):
            return normalize_domain(domain)

    domain_candidates = re.findall(
        r"(https?://\S+|www\.\S+|\b[a-z0-9-]+\.(?:com|org|net|edu|gov|io|co)\b)",
        raw,
    )
    normalized_candidates = [normalize_domain(candidate) for candidate in domain_candidates]

    for candidate in normalized_candidates:
        if candidate in blocked:
            return candidate

    for blocked_domain in blocked:
        label = blocked_domain.split(".", 1)[0]
        if label and re.search(rf"\b{re.escape(label)}\b", raw):
            return blocked_domain

    for candidate in normalized_candidates:
        if candidate:
            return candidate

    return ""


def _looks_like_grant(text: str) -> bool:
    lower = (text or "").lower()
    return any(
        phrase in lower
        for phrase in [
            "fair reason",
            "good reason",
            "valid reason",
            "i'll give you",
            "you've got",
            "you have",
            "i'll allow",
            "i'll unblock",
            "alright",
            "okay",
            "sounds legitimate",
            "that works",
        ]
    )


def _looks_like_deny(text: str) -> bool:
    lower = (text or "").lower()
    return any(
        phrase in lower
        for phrase in [
            "that's a no",
            "that is a no",
            "not helping you study",
            "not for studying",
            "get back to work",
            "i'm not unblocking",
            "i am not unblocking",
            "denied",
            "can't allow",
            "cannot allow",
        ]
    )


def _extract_minutes(text: str) -> int:
    match = re.search(r"\b(\d{1,3})\s*(?:minutes?|mins?)\b", text.lower())
    if match:
        return max(1, min(120, int(match.group(1))))
    return 30


def _resolve_action_domain(candidate: str) -> str:
    normalized = normalize_domain(candidate)
    if not normalized:
        return _pending_domain

    blocked = set(get_blocked_domains())
    pending = normalize_domain(_pending_domain)
    if normalized in blocked or not pending:
        return normalized

    if pending in blocked and normalized not in blocked:
        if normalized.startswith(("unblock", "block", "allow", "grant")):
            return pending
        collapsed_pending = pending.replace(".", "")
        collapsed_candidate = normalized.replace(".", "")
        if collapsed_pending and collapsed_pending in collapsed_candidate:
            return pending

    if normalized.startswith("unblock") or normalized.startswith("block"):
        suffix = normalized.removeprefix("unblock").removeprefix("block").lstrip(".-")
        suffix_domain = normalize_domain(suffix)
        if suffix_domain in blocked:
            return suffix_domain

    if pending and pending in blocked and pending in normalized:
        return pending

    return normalized


def _play_audio_via_pulse(wav_path: str) -> str:
    env = os.environ.copy()
    if _default_sink:
        env["PULSE_SINK"] = _default_sink
    playback = subprocess.run(
        ["paplay", wav_path],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if playback.returncode != 0:
        raise RuntimeError((playback.stderr or playback.stdout or "paplay playback failed").strip())
    return _default_sink


def _play_audio_via_alsa(wav_path: str) -> str:
    playback = subprocess.run(
        ["aplay", "-D", _alsa_playback_device, wav_path],
        check=False,
        capture_output=True,
        text=True,
    )
    if playback.returncode != 0:
        raise RuntimeError((playback.stderr or playback.stdout or "aplay playback failed").strip())
    return _alsa_playback_device


def set_debug_callback(callback) -> None:
    global debug_callback_ref
    debug_callback_ref = callback


def get_voice_status() -> dict:
    with _status_lock:
        return {
            "running": bool(_voice_thread and _voice_thread.is_alive()),
            "state": _voice_state,
            "is_speaking": is_speaking,
            "last_heard": _last_heard,
            "last_error": _last_error,
            "listening_enabled": _listening_enabled,
            "armed_until": _armed_until,
        }


def get_conversation_transcript() -> list[dict]:
    items = []
    for message in conversation_history[-40:]:
        role = message.get("role", "assistant")
        text = (message.get("content") or "").strip()
        if not text:
            continue
        if role == "assistant":
            spoken_lines = []
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("ACTION_"):
                    continue
                spoken_lines.append(stripped)
            text = " ".join(spoken_lines).strip()
            text = ACTION_GRANT_RE.sub("", text)
            text = ACTION_DENY_RE.sub("", text)
            text = re.sub(r"\s{2,}", " ", text).strip(" -:")
            if not text:
                continue
        items.append({"role": role, "text": text})
    return items


def _find_input_device_index() -> int | None:
    p = pyaudio.PyAudio()
    try:
        preferred = _preferred_input_name.lower()
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            name = str(info.get("name", ""))
            if info.get("maxInputChannels", 0) > 0 and preferred in name.lower():
                return i
        return None
    finally:
        p.terminate()


def get_rms(data):
    count = len(data) // 2
    shorts = struct.unpack("%dh" % count, data)
    sum_squares = sum(s * s for s in shorts)
    rms = (sum_squares / count) ** 0.5
    return rms


def record_until_silence():
    """Record from mic until silence detected. Returns wav path or None."""
    input_device_index = _find_input_device_index()
    p = pyaudio.PyAudio()
    sample_width = p.get_sample_size(FORMAT)

    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=input_device_index,
        frames_per_buffer=CHUNK
    )
    if input_device_index is not None:
        try:
            device_name = p.get_device_info_by_index(input_device_index).get("name", "")
            _push_debug("audio_input", f"Using mic: {device_name}")
        except Exception:
            pass
    else:
        _push_debug("audio_input", "Preferred Reachy mic unavailable, using fallback input device")

    _set_state("listening")
    print("[LISTENING...]")
    frames = []
    silent_chunks = 0
    has_speech = False
    max_chunks = int(RATE / CHUNK * MAX_RECORD_SECONDS)
    silence_chunks_needed = int(RATE / CHUNK * SILENCE_DURATION)

    for _ in range(max_chunks):
        data = stream.read(CHUNK, exception_on_overflow=False)
        rms = get_rms(data)
        frames.append(data)

        if rms > SILENCE_THRESHOLD:
            has_speech = True
            silent_chunks = 0
        elif has_speech:
            silent_chunks += 1
            if silent_chunks >= silence_chunks_needed:
                break

    stream.stop_stream()
    stream.close()
    p.terminate()

    if not has_speech:
        return None

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wf = wave.open(tmp.name, "wb")
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(sample_width)
    wf.setframerate(RATE)
    wf.writeframes(b"".join(frames))
    wf.close()
    return tmp.name


def transcribe(wav_path):
    """Send wav to Whisper, return text."""
    try:
        with open(wav_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="en"
            )
        os.remove(wav_path)
        text = result.text.strip()
        if text:
            _set_last_heard(text)
            _push_debug("user", text)
        print(f"[HEARD]: {text}")
        return text
    except Exception as e:
        _set_last_error(str(e))
        _push_debug("transcribe_error", str(e))
        print(f"[WHISPER ERROR]: {e}")
        try:
            os.remove(wav_path)
        except Exception:
            pass
        return ""


def speak(text):
    """Convert text to speech using OpenAI TTS and play through speakers."""
    global is_speaking
    is_speaking = True
    _set_state("speaking")
    _push_debug("robot", text)
    print(f"[ROBOT SPEAKING]: {text}")

    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text,
            speed=0.95
        )
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(response.content)
        tmp.close()
        wav_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        try:
            decode = subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", tmp.name, "-ar", "16000", "-ac", "2", wav_path],
                check=False,
                capture_output=True,
                text=True,
            )
            if decode.returncode != 0:
                raise RuntimeError((decode.stderr or "ffmpeg decode failed").strip())

            output_target = None
            if _pulse_playback_enabled:
                try:
                    output_target = _play_audio_via_pulse(wav_path)
                    _push_debug("audio_output", f"Using speaker sink: {output_target}")
                except Exception as pulse_exc:
                    _push_debug("audio_output", f"Pulse playback failed, falling back to ALSA: {pulse_exc}")

            if output_target is None:
                output_target = _play_audio_via_alsa(wav_path)
                _push_debug("audio_output", f"Using speaker ALSA device: {output_target}")
            _set_last_error("")
        finally:
            try:
                os.remove(wav_path)
            except Exception:
                pass
        try:
            os.remove(tmp.name)
        except Exception:
            pass

        # Reachy physical reaction
        if reachy_ref:
            lower = text.lower()
            if any(w in lower for w in [
                "okay", "alright", "fair", "granted",
                "sure", "good reason", "valid", "earned"
            ]):
                try:
                    reachy_ref.nod_yes()
                except Exception:
                    pass
            elif any(w in lower for w in [
                "no", "deny", "denied", "sorry",
                "not enough", "not for studying", "get back"
            ]):
                try:
                    reachy_ref.shake_no()
                except Exception:
                    pass

    except Exception as e:
        _set_last_error(str(e))
        _push_debug("tts_error", str(e))
        print(f"[TTS ERROR]: {e}")
    finally:
        is_speaking = False
        if _should_listen():
            _arm_listening(FOLLOWUP_GRACE_SECONDS)
            _set_state("listening")
        else:
            _set_state("sleeping")


def update_dns(domain, grant=True, minutes=30):
    """Update allowlist through the existing StudyGuard DNS path."""
    normalized = normalize_domain(domain)
    if not normalized:
        print(f"[DNS ERROR]: invalid domain: {domain}")
        return

    try:
        if grant:
            asyncio.run(update_dns_allowlist(normalized, minutes))
            print(f"[DNS] dnsmasq restarted — {normalized} is now UNBLOCKED")
            _push_debug("decision", f"GRANT {normalized} for {minutes} minutes")
        else:
            print(f"[DNS] {normalized} remains BLOCKED")
            _push_debug("decision", f"DENY {normalized}")
    except Exception as e:
        _set_last_error(str(e))
        _push_debug("dns_error", str(e))
        print(f"[DNS ERROR]: {e}")


def get_ai_response(user_text):
    """Send message to GPT-4o with full conversation history."""
    global conversation_history, _pending_domain

    # Build context from current study stats
    context = "Current study session — "
    if state_manager_ref:
        try:
            study_min = int(state_manager_ref.get_study_seconds_today()) // 60
            distracted_min = int(state_manager_ref.get_distracted_seconds_today()) // 60
            current_state = state_manager_ref.get_current_state()
            context += (
                f"studied {study_min} minutes today, "
                f"distracted {distracted_min} minutes, "
                f"currently {current_state}."
            )
        except Exception:
            context += "stats unavailable."
    else:
        context += "stats unavailable."

    detected_domain = _detect_domain_from_text(user_text)
    if detected_domain:
        _pending_domain = detected_domain
        context += f" Current requested domain: {_pending_domain}."
    elif _pending_domain:
        context += f" Current requested domain: {_pending_domain}."

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": context},
        *conversation_history[-20:],
        {"role": "user", "content": user_text}
    ]

    try:
        _set_state("thinking")
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.75,
            max_tokens=120
        )
        full_reply = resp.choices[0].message.content.strip()

        conversation_history.append(
            {"role": "user", "content": user_text}
        )
        conversation_history.append(
            {"role": "assistant", "content": full_reply}
        )

        action_taken = False
        grant_match = ACTION_GRANT_RE.search(full_reply)
        deny_match = ACTION_DENY_RE.search(full_reply)
        spoken = ACTION_GRANT_RE.sub("", full_reply)
        spoken = ACTION_DENY_RE.sub("", spoken)
        spoken = re.sub(r"\s{2,}", " ", spoken.replace("\n", " ")).strip(" -:")

        if grant_match:
            domain = _resolve_action_domain(grant_match.group(1))
            minutes = int(grant_match.group(2))
            if domain:
                print(f"[ACTION] GRANT {domain} for {minutes} minutes")
                threading.Thread(
                    target=update_dns,
                    args=(domain, True, minutes),
                    daemon=True
                ).start()
                _pending_domain = ""
                action_taken = True

        elif deny_match:
            domain = _resolve_action_domain(deny_match.group(1))
            if domain:
                print(f"[ACTION] DENY {domain}")
                threading.Thread(
                    target=update_dns,
                    args=(domain, False, 0),
                    daemon=True
                ).start()
                _pending_domain = ""
                action_taken = True

        if not action_taken and _pending_domain:
            if _looks_like_grant(spoken) and not _looks_like_deny(spoken):
                minutes = _extract_minutes(spoken)
                print(f"[ACTION] INFERRED GRANT {_pending_domain} for {minutes} minutes")
                threading.Thread(
                    target=update_dns,
                    args=(_pending_domain, True, minutes),
                    daemon=True
                ).start()
                action_taken = True
                _pending_domain = ""
            elif _looks_like_deny(spoken):
                print(f"[ACTION] INFERRED DENY {_pending_domain}")
                threading.Thread(
                    target=update_dns,
                    args=(_pending_domain, False, 0),
                    daemon=True
                ).start()
                action_taken = True
                _pending_domain = ""

        if _pending_domain and any(
            phrase in spoken.lower() for phrase in ["what exactly", "what do you need it for", "why do you need", "what do you need"]
        ):
            _push_debug("pending_domain", _pending_domain)
        if spoken:
            _push_debug("assistant", spoken)
        return spoken if spoken else "Got it."

    except Exception as e:
        _set_last_error(str(e))
        _push_debug("gpt_error", str(e))
        print(f"[GPT ERROR]: {e}")
        return "Sorry, I had a brain freeze. Try again."


def voice_loop():
    """Main loop. Mic is muted until explicitly armed from the dashboard."""
    time.sleep(4)  # wait for server to fully start

    _set_state("sleeping")
    print("[VOICE] Starting voice loop...")
    startup_line = "StudyGuard is online. Arm the mic when you want me to listen."
    conversation_history.append({"role": "assistant", "content": startup_line})
    speak(startup_line)
    _set_state("sleeping")

    while True:
        try:
            if not _should_listen():
                _set_state("sleeping")
                time.sleep(0.2)
                continue

            if is_speaking:
                time.sleep(0.3)
                continue

            wav_path = record_until_silence()

            if not wav_path:
                continue

            text = transcribe(wav_path)

            if not text or len(text.strip()) < 3:
                continue

            reply = get_ai_response(text)

            if reply:
                speak(reply)

        except KeyboardInterrupt:
            break
        except Exception as e:
            _set_last_error(str(e))
            _push_debug("voice_error", str(e))
            print(f"[VOICE LOOP ERROR]: {e}")
            time.sleep(2)
            continue


def start_voice_loop(state_manager=None, reachy=None):
    """Called from main.py on startup."""
    global state_manager_ref, reachy_ref, _voice_thread
    state_manager_ref = state_manager
    reachy_ref = reachy
    if _voice_thread and _voice_thread.is_alive():
        print("[VOICE] Voice loop already running")
        return
    _voice_thread = threading.Thread(target=voice_loop, daemon=True)
    _voice_thread.start()
    print("[VOICE] Voice loop thread started")
