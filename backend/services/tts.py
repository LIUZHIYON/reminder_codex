import os
import asyncio
import subprocess
from config import AUDIO_DIR

os.makedirs(AUDIO_DIR, exist_ok=True)

def _get_audio_path(reminder_id):
    return os.path.join(AUDIO_DIR, f"reminder_{reminder_id}.wav")

def _fix_extension(path, expected_fmt):
    base, ext = os.path.splitext(path)
    correct_ext = ".wav" if expected_fmt == "wav" else ".mp3"
    if ext.lower() != correct_ext:
        new_path = base + correct_ext
        if os.path.exists(path):
            os.rename(path, new_path)
        return new_path
    return path

def generate_audio_sync(reminder_id: int, title: str, description: str = "") -> str:
    text = f"\u53ee\u549a\uff01\u63d0\u9192\u65f6\u95f4\u5230\u5566\uff01{title}"
    if description:
        text += f"\u3002{description}"
    text += "\u3002\u522b\u5fd8\u4e86\u54e6\uff01"

    # Delete old file first to ensure fresh generation
    audio_path = _get_audio_path(reminder_id)
    if os.path.exists(audio_path):
        try:
            os.remove(audio_path)
            print(f"[TTS] Removed old audio: {os.path.basename(audio_path)}")
        except:
            pass

    # PowerShell TTS → WAV
    result = _try_powershell(text, reminder_id)
    if result:
        return _fix_extension(result, "wav")

    # pyttsx3 → WAV
    result = _try_pyttsx3(text, reminder_id)
    if result:
        return _fix_extension(result, "wav")

    # gTTS → MP3
    result = _try_gtts(text, reminder_id)
    if result:
        return _fix_extension(result, "mp3")

    # edge-tts → MP3
    result = _try_edge_tts_sync(text, reminder_id)
    if result:
        return _fix_extension(result, "mp3")

    print(f"[TTS] All backends failed")
    return ""

def _try_powershell(text, reminder_id):
    audio_path = _get_audio_path(reminder_id)
    try:
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "try { $s.SelectVoice('Microsoft Huihui Desktop') } catch { "
            "  try { $s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female) } catch {} "
            "}; "
            f"$s.SetOutputToWaveFile('{audio_path}'); "
            f"$s.Speak('{text.replace(chr(39), chr(39)+chr(39))}'); "
            "$s.Dispose()"
        )
        subprocess.run(["powershell","-NoProfile","-Command",script], check=True, timeout=10,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.getsize(audio_path) > 1000:
            print(f"[TTS] PowerShell: OK")
            return audio_path
    except Exception as e:
        print(f"[TTS] PowerShell failed: {e}")
    return ""

def _try_pyttsx3(text, reminder_id):
    audio_path = _get_audio_path(reminder_id)
    try:
        import pyttsx3
        engine = pyttsx3.init()
        for v in engine.getProperty("voices"):
            if "huihui" in v.name.lower():
                engine.setProperty("voice", v.id); break
            elif "female" in v.name.lower():
                engine.setProperty("voice", v.id)
        engine.setProperty("rate", 180)
        engine.save_to_file(text, audio_path)
        engine.runAndWait()
        if os.path.getsize(audio_path) > 1000:
            print(f"[TTS] pyttsx3: OK")
            return audio_path
    except Exception as e:
        print(f"[TTS] pyttsx3 failed: {e}")
    return ""

def _try_gtts(text, reminder_id):
    audio_path = _get_audio_path(reminder_id)
    try:
        import urllib.request, socket; socket.setdefaulttimeout(5)
        from gtts import gTTS
        gTTS(text, lang="zh-CN", slow=False).save(audio_path)
        if os.path.getsize(audio_path) > 100:
            print(f"[TTS] gTTS: OK")
            return audio_path
    except Exception as e:
        print(f"[TTS] gTTS failed: {e}")
    return ""

def _try_edge_tts_sync(text, reminder_id):
    audio_path = _get_audio_path(reminder_id)
    try:
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        result = loop.run_until_complete(asyncio.wait_for(
            _edge_async(text, audio_path), timeout=10))
        loop.close()
        if result and os.path.getsize(audio_path) > 100:
            print(f"[TTS] edge-tts: OK")
            return audio_path
    except asyncio.TimeoutError:
        print(f"[TTS] edge-tts timed out")
    except Exception as e:
        print(f"[TTS] edge-tts failed: {e}")
    return ""

async def _edge_async(text, audio_path):
    import edge_tts
    c = edge_tts.Communicate(text, voice="zh-CN-XiaoyiNeural", rate="+15%", volume="+30%")
    await c.save(audio_path)
    return True
