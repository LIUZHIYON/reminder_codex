import os, json, sys
from datetime import datetime

def check_board_reminders():
    bf = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "board_reminders.json")
    if not os.path.exists(bf):
        return
    try:
        recs = json.load(open(bf, "r", encoding="utf-8"))
    except:
        return
    now = datetime.now()
    changed = False
    for r in recs:
        s = r.get("status", "")
        if s not in ("received", "pending"):
            continue
        rt = r.get("reminder_time", "")
        if not rt:
            continue
        try:
            rtd = datetime.fromisoformat(rt.replace("T", " "))
        except:
            continue
        if rtd <= now:
            if now - rtd > timedelta(minutes=5):
                r["status"] = "missed"
                changed = True
                print("[Board] Skipped (past): " + title)
                continue
            title = r.get("title", "") or r.get("content", "")
            content = r.get("content", "") or title
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
                    print("[Board] Auto-played: " + title)
            except Exception as e:
                print("[Board] TTS error: " + str(e))
    if changed:
        json.dump(recs, open(bf, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
