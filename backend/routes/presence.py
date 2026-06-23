import os, json
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRESENCE_FILE = os.path.join(BASE, "board_presence.json")
CACHE_FILE = os.path.join(BASE, "board_reminders.json")

def get_presence():
    if os.path.exists(PRESENCE_FILE):
        try:
            d = json.load(open(PRESENCE_FILE, "r", encoding="utf-8"))
            return d.get("present", True)
        except:
            pass
    return True

def set_presence(present):
    os.makedirs(os.path.dirname(PRESENCE_FILE), exist_ok=True)
    with open(PRESENCE_FILE, "w", encoding="utf-8") as f:
        json.dump({"present": present, "updated_at": datetime.now().isoformat()}, f)

def process_reminders():
    if not os.path.exists(CACHE_FILE):
        return
    try:
        recs = json.load(open(CACHE_FILE, "r", encoding="utf-8"))
    except:
        return
    now = datetime.now()
    changed = False
    present = get_presence()
    for r in recs:
        s = r.get("status", "")
        if s not in ("received", "pending", "delayed"):
            continue
        rt = r.get("reminder_time", "")
        if not rt:
            continue
        try:
            rtd = datetime.fromisoformat(rt.replace("T", " "))
        except:
            continue
        if rtd > now:
            continue
        title = r.get("title", "") or r.get("content", "")
        content = r.get("content", "") or title
        if s == "delayed":
            nxt = r.get("next_check", "")
            if nxt:
                try:
                    if datetime.fromisoformat(nxt) > now:
                        continue
                except:
                    pass
            tm = r.get("timeout_minutes", 60)
            if rtd and now - rtd > timedelta(minutes=tm):
                r["status"] = "timeout"
                r["timeout_reason"] = "absent_too_long"
                changed = True
                print(f"[Presence] Timeout (total): {title}")
                continue
        if not present:
            dc = r.get("presence_delay_count", 0)
            tm = r.get("timeout_minutes", 60)
            if dc * 10 >= tm:
                r["status"] = "timeout"
                r["timeout_reason"] = "absent_too_long"
                changed = True
                print(f"[Presence] Timeout: {title}")
                continue
            r["status"] = "delayed"
            r["presence_delay_count"] = dc + 1
            r["next_check"] = (datetime.now() + timedelta(minutes=10)).isoformat()
            changed = True
            print(f"[Presence] Delayed: {title} #{dc+1}")
            continue
        aid = abs(hash(title + rt)) % 100000
        try:
            from services.tts import generate_audio_sync as _gen
            ap = _gen(aid, title, content)
            if ap:
                from player import player as _pl
                _pl.play(ap, True)
                r["status"] = "played"
                r["audio_file"] = ap
                changed = True
                print(f"[Presence] Played: {title}")
        except Exception as e:
            print(f"[Presence] TTS error: {e}")
    if changed:
        json.dump(recs, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
