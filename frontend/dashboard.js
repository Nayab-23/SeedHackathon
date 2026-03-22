(function () {
  "use strict";

  const LOCK_DOMAINS = ["youtube.com", "instagram.com", "tiktok.com", "twitter.com", "reddit.com"];
  const LISTEN_WINDOW_SECONDS = 20;
  const stateLabels = {
    studying: "STUDYING",
    distracted: "DISTRACTED",
    phone: "PHONE DETECTED",
  };
  const voiceLabels = {
    sleeping: "SLEEPING",
    listening: "LISTENING",
    thinking: "THINKING",
    speaking: "SPEAKING",
  };

  function $(id) {
    return document.getElementById(id);
  }

  function fmtDur(sec) {
    sec = Math.round(Number(sec) || 0);
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    if (h > 0) return h + "h " + m + "m";
    return m + "m";
  }

  function fmtDate(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
  }

  function fmtTime(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }

  function fmtExpires(iso) {
    if (!iso) return '<span class="exp-perm">permanent</span>';
    const d = new Date(iso);
    const now = new Date();
    if (d <= now) return '<span class="exp-perm">expired</span>';
    const mins = Math.round((d - now) / 60000);
    return '<span class="exp-ok">' + mins + " min</span>";
  }

  function fmtSecs(sec) {
    sec = Math.max(0, Math.round(Number(sec) || 0));
    return sec + "s";
  }

  function focusPct(study, dist) {
    const total = study + dist;
    if (total <= 0) return "--";
    return Math.round((100 * study) / total) + "%";
  }

  function esc(s) {
    const node = document.createElement("div");
    node.textContent = s == null ? "" : String(s);
    return node.innerHTML;
  }

  function setClock() {
    $("clock").textContent = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  function setSidebarState(open) {
    const sidebar = $("sidebar");
    if (!sidebar) return;
    sidebar.classList.toggle("open", open);
  }

  function bindNav() {
    const toggle = $("navToggle");
    if (toggle) {
      toggle.addEventListener("click", function () {
        const sidebar = $("sidebar");
        setSidebarState(!(sidebar && sidebar.classList.contains("open")));
      });
    }

    document.querySelectorAll(".nav-link").forEach(function (btn) {
      btn.addEventListener("click", function () {
        document.querySelectorAll(".nav-link").forEach((node) => node.classList.remove("active"));
        btn.classList.add("active");
        const target = document.getElementById(btn.dataset.target);
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
        if (window.innerWidth <= 900) setSidebarState(false);
      });
    });
  }

  function startCamStream() {
    const img = $("cam");
    let refreshTimer = null;
    let inFlight = false;

    async function refresh() {
      if (inFlight) return;
      inFlight = true;
      try {
        const res = await fetch("/api/camera?t=" + Date.now(), { cache: "no-store" });
        if (!res.ok) throw new Error("camera unavailable");
        const blob = await res.blob();
        const nextUrl = URL.createObjectURL(blob);
        const prevUrl = img.dataset.objectUrl;
        img.onload = function () {
          img.classList.remove("stale");
          $("cameraChip").textContent = "camera link live";
          if (prevUrl) URL.revokeObjectURL(prevUrl);
        };
        img.onerror = function () {
          img.classList.add("stale");
          $("cameraChip").textContent = "camera reconnecting";
          URL.revokeObjectURL(nextUrl);
        };
        img.dataset.objectUrl = nextUrl;
        img.src = nextUrl;
      } catch (_err) {
        img.classList.add("stale");
        $("cameraChip").textContent = "camera reconnecting";
      } finally {
        inFlight = false;
      }
    }

    refresh();
    refreshTimer = setInterval(refresh, 120);
    window.addEventListener("beforeunload", function () {
      if (refreshTimer) clearInterval(refreshTimer);
      const objectUrl = img.dataset.objectUrl;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    });
  }

  function formatEvent(ev) {
    const type = (ev.event_type || "").toLowerCase();
    const detail = ev.detail || "";

    if (type === "studying") return { icon: "◼", title: "studying", sub: "child is focused on schoolwork" };
    if (type === "distracted") return { icon: "◼", title: "distracted", sub: "attention moved off task" };
    if (type === "phone" || type === "phone_detected") return { icon: "◼", title: "phone detected", sub: "possible phone use" };
    if (type === "site_granted") {
      const dom = (detail.match(/domain=([^|]+)/) || [])[1] || "site";
      const mins = (detail.match(/mins=(\d+)/) || [])[1];
      const reason = (detail.match(/reason=([^|]+)/) || [])[1];
      const sub = [mins ? "granted for " + mins + " min" : "", reason || ""].filter(Boolean).join(" · ");
      return { icon: "◼", title: dom + " granted", sub: sub || detail };
    }
    if (type === "site_denied") {
      const dom = (detail.match(/domain=([^|]+)/) || [])[1] || "site";
      const reason = (detail.match(/reason=([^|]+)/) || [])[1];
      return { icon: "◼", title: dom + " denied", sub: reason || detail };
    }
    if (type === "site_expired") return { icon: "◼", title: "site access expired", sub: detail };
    if (type === "voice_wake") return { icon: "◼", title: "voice wake", sub: "wake phrase detected" };
    if (type === "voice_domain_heard") return { icon: "◼", title: "domain heard", sub: detail };
    if (type === "voice_session_start") return { icon: "◼", title: "voice session started", sub: detail };
    if (type === "voice_argument_heard") return { icon: "◼", title: "voice argument heard", sub: detail.replace(/^domain=[^|]+\|\s*transcript=/, "") };
    if (type === "voice_session_complete") return { icon: "◼", title: "voice session complete", sub: detail };
    return { icon: "◼", title: (type || "event").replace(/_/g, " "), sub: detail };
  }

  function formatDnsKind(kind, blocked) {
    if (blocked) return "blocked";
    const value = (kind || "dns").toLowerCase();
    if (value === "query") return "query";
    if (value === "forwarded") return "forwarded";
    if (value === "reply") return "reply";
    if (value === "cached") return "cached";
    if (value === "config") return "local rule";
    return "dns";
  }

  function updateMicButton(voice) {
    const btn = $("micBtn");
    if (!btn) return;
    const enabled = !!voice.listening_enabled;
    btn.dataset.armed = enabled ? "true" : "false";
    const armedUntil = Number(voice.armed_until || 0);
    const remaining = armedUntil ? Math.max(0, Math.ceil(armedUntil - Date.now() / 1000)) : 0;
    btn.classList.remove("btn-primary", "btn-danger");
    if (enabled) {
      btn.classList.add("btn-danger");
      btn.textContent = remaining > 0 ? "Mute Mic (" + fmtSecs(remaining) + ")" : "Mute Mic";
    } else {
      btn.classList.add("btn-primary");
      btn.textContent = "Arm Mic";
    }
  }

  async function pollStatus() {
    try {
      const [statusRes, healthRes, voiceRes] = await Promise.all([
        fetch("/api/status"),
        fetch("/api/health"),
        fetch("/api/voice/status"),
      ]);
      if (!statusRes.ok || !healthRes.ok || !voiceRes.ok) return;

      const status = await statusRes.json();
      const health = await healthRes.json();
      const voice = await voiceRes.json();
      const state = status.state || "studying";
      const voiceState = status.voice_state || "sleeping";
      const app = $("appShell");

      app.classList.remove("state-studying", "state-distracted", "state-phone");
      app.classList.add("state-" + state);

      $("badge").textContent = stateLabels[state] || state.toUpperCase();
      $("voiceBadge").textContent = voiceLabels[voiceState] || voiceState.toUpperCase();
      $("studyVal").textContent = fmtDur(status.study_seconds_today);
      $("distVal").textContent = fmtDur(status.distracted_seconds_today);
      $("focusVal").textContent = focusPct(Number(status.study_seconds_today) || 0, Number(status.distracted_seconds_today) || 0);
      $("stateVal").textContent = state;
      $("voiceStateVal").textContent = voiceState;
      $("agoraVal").textContent = voice.agent_running ? "online" : "offline";
      $("agentStatus").textContent = voice.agent_running ? "online" : "offline";
      $("cameraStatus").textContent = health.camera ? "live" : "offline";
      $("reachyStatus").textContent = health.reachy ? "live" : "offline";
      $("cameraHealthVal").textContent = health.camera ? "live" : "offline";
      $("reachyHealthVal").textContent = health.reachy ? "connected" : "offline";
      $("uptimeVal").textContent = fmtDur(health.uptime_seconds || 0);
      $("cameraMeta").textContent = health.camera
        ? "frame age " + ((health.camera_frame_age_seconds == null) ? "0" : health.camera_frame_age_seconds) + "s"
        : "camera unavailable";
      $("cameraChip").textContent = health.camera ? "camera link live" : "camera unavailable";
      updateMicButton(voice);
    } catch (_err) {}
  }

  async function pollEvents() {
    try {
      const res = await fetch("/api/events?limit=20");
      if (!res.ok) return;
      const rows = await res.json();
      const feed = $("feed");
      if (!rows.length) {
        feed.innerHTML = '<div class="feed-empty">No activity yet.</div>';
        return;
      }
      feed.innerHTML = rows.map(function (ev) {
        const item = formatEvent(ev);
        return (
          '<div class="feed-item">' +
            '<div class="fi-ico">' + item.icon + "</div>" +
            '<div class="fi-body">' +
              '<div class="fi-title">' + esc(item.title) + "</div>" +
              (item.sub ? '<div class="fi-sub">' + esc(item.sub) + "</div>" : "") +
            "</div>" +
            '<div class="fi-time">' + fmtTime(ev.timestamp) + "</div>" +
          "</div>"
        );
      }).join("");
    } catch (_err) {}
  }

  async function pollVoiceDebug() {
    try {
      const res = await fetch("/api/voice/debug");
      if (!res.ok) return;
      const rows = await res.json();
      const feed = $("voiceFeed");
      if (!rows.length) {
        feed.innerHTML = '<div class="feed-empty">No voice debug yet.</div>';
        return;
      }
      feed.innerHTML = rows.map(function (row) {
        return (
          '<div class="feed-item">' +
            '<div class="fi-ico">◼</div>' +
            '<div class="fi-body">' +
              '<div class="voice-kind">' + esc(row.kind || "info") + "</div>" +
              '<div class="fi-title">' + esc(row.text || "") + "</div>" +
            "</div>" +
            '<div class="fi-time">' + fmtTime(row.timestamp) + "</div>" +
          "</div>"
        );
      }).join("");
    } catch (_err) {}
  }

  async function pollDnsLogs() {
    try {
      const res = await fetch("/api/logs/dns?limit=120");
      if (!res.ok) return;
      const rows = await res.json();
      const feed = $("dnsFeed");
      if (!rows.length) {
        feed.innerHTML = '<div class="feed-empty">No DNS traffic yet.</div>';
        return;
      }
      feed.innerHTML = rows.map(function (row) {
        const classes = ["feed-item", "log-item"];
        if (row.blocked) classes.push("blocked");
        const sub = [
          row.client ? "from " + row.client : "",
          row.outcome || "",
          !row.outcome && row.raw ? row.raw : "",
        ].filter(Boolean).join(" · ");
        return (
          '<div class="' + classes.join(" ") + '">' +
            '<div class="fi-ico">' + (row.blocked ? "■" : "◼") + "</div>" +
            '<div class="fi-body">' +
              '<div class="voice-kind ' + (row.blocked ? "kind-blocked" : "kind-neutral") + '">' + esc(formatDnsKind(row.kind, row.blocked)) + "</div>" +
              '<div class="fi-title">' + esc(row.domain || "dns event") + "</div>" +
              (sub ? '<div class="fi-sub">' + esc(sub) + "</div>" : "") +
            "</div>" +
            '<div class="fi-time">' + esc(row.timestamp_text || "—") + "</div>" +
          "</div>"
        );
      }).join("");
    } catch (_err) {}
  }

  async function pollConversation() {
    try {
      const res = await fetch("/api/voice/conversation");
      if (!res.ok) return;
      const rows = await res.json();
      const feed = $("conversationFeed");
      if (!rows.length) {
        feed.innerHTML = '<div class="feed-empty">No conversation yet.</div>';
        return;
      }
      feed.innerHTML = rows.map(function (row) {
        const role = row.role === "user" ? "child" : "studyguard";
        return (
          '<div class="feed-item">' +
            '<div class="fi-ico">◼</div>' +
            '<div class="fi-body">' +
              '<div class="voice-kind">' + esc(role) + "</div>" +
              '<div class="fi-title">' + esc(row.text || "") + "</div>" +
            "</div>" +
          "</div>"
        );
      }).join("");
    } catch (_err) {}
  }

  async function pollBlk() {
    try {
      const res = await fetch("/api/blocklist");
      if (!res.ok) return;
      const list = await res.json();
      const body = $("blkBody");
      const empty = $("blkEmpty");
      if (!list.length) {
        body.innerHTML = "";
        empty.hidden = false;
        return;
      }
      empty.hidden = true;
      body.innerHTML = list.map(function (row) {
        return (
          "<tr>" +
            '<td class="mono">' + esc(row.domain) + "</td>" +
            "<td>" + fmtDate(row.added_at) + "</td>" +
            '<td><button type="button" class="btn btn-danger" data-rm-domain="' + esc(row.domain) + '">Remove</button></td>' +
          "</tr>"
        );
      }).join("");

      body.querySelectorAll("[data-rm-domain]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          rmBlk(btn.getAttribute("data-rm-domain"));
        });
      });
    } catch (_err) {}
  }

  async function pollAlw() {
    try {
      const res = await fetch("/api/allowlist");
      if (!res.ok) return;
      const list = await res.json();
      const body = $("alwBody");
      const empty = $("alwEmpty");
      if (!list.length) {
        body.innerHTML = "";
        empty.hidden = false;
        return;
      }
      empty.hidden = true;
      body.innerHTML = list.map(function (row) {
        return (
          "<tr>" +
            '<td class="mono">' + esc(row.domain) + "</td>" +
            "<td>" + esc(row.reason || "—") + "</td>" +
            "<td>" + fmtExpires(row.expires_at) + "</td>" +
          "</tr>"
        );
      }).join("");
    } catch (_err) {}
  }

  async function addBlock() {
    const input = $("blkIn");
    const domain = (input.value || "").trim().toLowerCase();
    if (!domain) return;
    try {
      const res = await fetch("/api/blocklist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain: domain }),
      });
      if (res.status === 409) {
        alert("Already blocked.");
        return;
      }
      if (!res.ok) {
        alert("Could not block domain.");
        return;
      }
      input.value = "";
      pollBlk();
      pollEvents();
    } catch (_err) {
      alert("Network error.");
    }
  }

  async function rmBlk(domain) {
    try {
      await fetch("/api/blocklist/" + encodeURIComponent(domain), { method: "DELETE" });
      pollBlk();
      pollEvents();
    } catch (_err) {}
  }

  async function lockDown() {
    if (!confirm("Block the default social domains?")) return;
    for (const domain of LOCK_DOMAINS) {
      try {
        await fetch("/api/blocklist", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ domain: domain }),
        });
      } catch (_err) {}
    }
    pollBlk();
    pollEvents();
  }

  async function postOverride(payload) {
    const res = await fetch("/api/voice/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error((await res.text()) || "Request failed");
    }
    pollAlw();
    pollEvents();
  }

  async function grantOverride() {
    const domain = ($("ovrDomain").value || "").trim();
    const minutes = Number($("ovrMinutes").value || 30);
    if (!domain) return;
    try {
      await postOverride({ action: "grant", domain: domain, minutes: minutes });
    } catch (err) {
      alert("Grant failed: " + (err && err.message ? err.message : String(err)));
    }
  }

  async function denyOverride() {
    const domain = ($("ovrDomain").value || "").trim();
    if (!domain) return;
    try {
      await postOverride({ action: "deny", domain: domain });
    } catch (err) {
      alert("Deny failed: " + (err && err.message ? err.message : String(err)));
    }
  }

  async function toggleMic() {
    const btn = $("micBtn");
    const enabled = btn && btn.dataset.armed === "true";
    try {
      const res = await fetch("/api/voice/listening", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: !enabled,
          duration_seconds: LISTEN_WINDOW_SECONDS,
        }),
      });
      if (!res.ok) throw new Error("Could not change mic state");
      const voice = await res.json();
      if (btn) {
        btn.dataset.armed = voice.listening_enabled ? "true" : "false";
      }
      updateMicButton(voice);
    } catch (err) {
      alert("Mic control failed: " + (err && err.message ? err.message : String(err)));
    }
  }

  function bindActions() {
    $("addBlockBtn").addEventListener("click", addBlock);
    $("grantBtn").addEventListener("click", grantOverride);
    $("denyBtn").addEventListener("click", denyOverride);
    $("lockBtn").addEventListener("click", lockDown);

    $("blkIn").addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") addBlock();
    });
    $("ovrDomain").addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") grantOverride();
    });
    $("micBtn").addEventListener("click", toggleMic);
  }

  function boot() {
    setClock();
    setInterval(setClock, 1000);
    bindNav();
    bindActions();
    startCamStream();
    pollStatus();
    pollEvents();
    pollBlk();
    pollAlw();
    pollConversation();
    pollVoiceDebug();
    pollDnsLogs();
    setInterval(pollStatus, 3000);
    setInterval(pollEvents, 4000);
    setInterval(pollAlw, 3000);
    setInterval(pollConversation, 2000);
    setInterval(pollVoiceDebug, 2000);
    setInterval(pollDnsLogs, 2000);
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
