"""
Flask Web 界面 - 查看提醒系统状态
"""
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
import os
import json
from datetime import datetime


def create_web_app(db, scheduler, tts_service, config):
    app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))
    CORS(app)

    @app.route("/")
    def index():
        stats = db.get_stats()
        return render_template("index.html", stats=stats)

    # ====== 提醒 CRUD ======

    @app.route("/api/reminders")
    def api_reminders():
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)
        status = request.args.get("status", None)
        reminders = db.get_reminders(limit=limit, offset=offset, status=status)
        return jsonify({"success": True, "data": reminders})


    @app.route("/api/reminders/create", methods=["POST"])
    def api_create_reminder():
        """???8001??????????????"""
        import json as _json
        raw = request.get_data(as_text=True)
        data = _json.loads(raw) if raw else {}
        content = data.get("content", "")
        reminder_time = data.get("reminder_time", "")
        if not content or not reminder_time:
            return jsonify({"success": False, "error": "content+reminder_time required"}), 400
        ok = db.add_reminder(content, reminder_time)
        if not ok:
            return jsonify({"success": False, "error": "reminder already exists"}), 409
        reminders = db.get_reminders(limit=1)
        rid = reminders[0]["id"] if reminders else None
        return jsonify({"success": True, "id": rid, "content": content, "reminder_time": reminder_time})

    @app.route("/api/reminders", methods=["POST"])
    def api_add_reminder():
        """手动添加提醒"""
        data = request.json
        content = data.get("content", "").strip()
        reminder_time = data.get("reminder_time", "").strip()
        if not content:
            return jsonify({"success": False, "message": "提醒内容不能为空"})
        if not reminder_time:
            return jsonify({"success": False, "message": "提醒时间不能为空"})
        ok = db.add_reminder(content, reminder_time)
        return jsonify({"success": ok, "message": "添加成功" if ok else "已存在相同的提醒"})

    @app.route("/api/reminders/<int:rid>", methods=["DELETE"])
    def api_delete_reminder(rid):
        """删除提醒"""
        ok = db.delete_reminder(rid)
        return jsonify({"success": ok, "message": "已删除" if ok else "未找到该提醒"})

    @app.route("/api/reminders/<int:rid>", methods=["PUT"])
    def api_update_reminder(rid):
        """修改提醒（内容和时间）"""
        data = request.json
        content = data.get("content", "").strip() or None
        reminder_time = data.get("reminder_time", "").strip() or None
        if not content and not reminder_time:
            return jsonify({"success": False, "message": "没有需要修改的内容"})
        ok, msg = db.update_reminder(rid, content=content, reminder_time=reminder_time)
        return jsonify({"success": ok, "message": msg})

    @app.route("/api/reminders/<int:rid>/status", methods=["POST"])
    def api_update_status(rid):
        status = request.json.get("status", "triggered")
        db.update_reminder_status(rid, status)
        return jsonify({"success": True})

    # ====== 音频 ======

    @app.route("/api/tts/generate")
    def api_tts_generate():
        """生成 TTS 音频（浏览器播放用）
        返回 MP3 或 WAV 文件，由 TTS 引擎决定格式。
        """
        text = request.args.get("text", "").strip()
        if not text:
            return jsonify({"success": False, "message": "文本不能为空"})
        filepath, err = tts_service.generate_audio_file(text)
        if not filepath:
            return jsonify({"success": False, "message": err or "生成失败"})
        # 根据文件后缀确定正确的 Content-Type
        ext = os.path.splitext(filepath)[1].lower()
        mimetypes = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg"}
        mime = mimetypes.get(ext, "audio/wav")
        return send_file(filepath, mimetype=mime)

    @app.route("/api/audio/<filename>")
    def api_serve_audio(filename):
        """提供已有音频文件"""
        filepath = os.path.join(config.BASE_DIR, "audio", filename)
        if not os.path.exists(filepath):
            return jsonify({"success": False, "message": "文件不存在"}), 404
        return send_file(filepath, mimetype="audio/wav")

    @app.route("/api/reminders/<int:rid>/replay", methods=["POST"])
    def api_replay_reminder(rid):
        """重新播报（在板子扬声器上播放）"""
        reminders = db.get_reminders(limit=100)
        target = None
        for r in reminders:
            if r["id"] == rid:
                target = r
                break
        if not target:
            return jsonify({"success": False, "message": "未找到该提醒"})
        content = target["content"]
        success, result = tts_service.speak(content)
        db.log_tts(rid, content, "replay" if success else "failed",
                   audio_file=result if success else result)
        return jsonify({"success": success, "message": result})

    # ====== 消息 / 日志 ======

    @app.route("/api/messages")
    def api_messages():
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)
        messages = db.get_chat_messages(limit=limit, offset=offset)
        return jsonify({"success": True, "data": messages})

    @app.route("/api/tts-logs")
    def api_tts_logs():
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)
        logs = db.get_tts_logs(limit=limit, offset=offset)
        return jsonify({"success": True, "data": logs})

    # ====== 状态 / 工具 ======

    @app.route("/api/stats")
    def api_stats():
        stats = db.get_stats()
        return jsonify({"success": True, "data": stats})

    @app.route("/api/current-time")
    def api_current_time():
        return jsonify({
            "success": True,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": datetime.now().timestamp()
        })

    @app.route("/api/refresh")
    def api_refresh():
        from .json_reader import parse_and_store
        count, msg = parse_and_store(db, config.JSON_FILE_PATH)
        return jsonify({"success": True, "message": msg, "count": count})

    @app.route("/api/trigger-check")
    def api_trigger_check():
        if scheduler:
            scheduler.run_once()
        return jsonify({"success": True, "message": "检查已触发"})

    @app.route("/api/scheduler/stats")
    def api_scheduler_stats():
        """获取调度器运行统计"""
        if scheduler:
            return jsonify({"success": True, "data": scheduler.get_stats()})
        return jsonify({"success": False, "message": "调度器未运行"})

    @app.route("/api/test-tts")
    def api_test_tts():
        text = request.args.get("text", "您好，这是一条测试语音。")
        success, result = tts_service.speak(text)
        return jsonify({"success": success, "message": result, "file": result if success else None})

    @app.route("/api/test-tts-web", methods=["POST"])
    def api_test_tts_web():
        """Web端测试TTS - 生成音频文件返回（不播报）"""
        data = request.json or {}
        text = data.get("text", "您好，这是一条测试语音。")
        filepath, err = tts_service.generate_audio_file(text)
        if filepath:
            return send_file(filepath, mimetype="audio/wav", as_attachment=False)
        return jsonify({"success": False, "message": err or "生成失败"})

    @app.route("/api/diagnostic")
    def api_diagnostic():
        """系统诊断 - 检查音频播放能力"""
        diag = tts_service.diagnostic()
        # 补充一些系统信息
        import platform
        diag["system"] = {
            "platform": platform.platform(),
            "python": platform.python_version(),
        }
        return jsonify({"success": True, "data": diag})

    return app
