from flask import Flask, request, jsonify, send_from_directory, render_template
import os
import uuid
import json
import time
from audio_utils import standardize_audio, check_audio_duration
import pyttsx3
from pptx import Presentation

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
PPT_FOLDER = os.path.join(UPLOAD_FOLDER, 'pptx')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PPT_FOLDER, exist_ok=True)

METADATA_PATH = os.path.join(UPLOAD_FOLDER, 'audio_metadata.json')
TEXT_TASK_PATH = os.path.join(UPLOAD_FOLDER, 'text_tasks.json')


def save_metadata(metadata):
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, 'r') as f:
            data = json.load(f)
    else:
        data = []
    data.append(metadata)
    with open(METADATA_PATH, 'w') as f:
        json.dump(data, f, indent=2)


def load_all_voices():
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, 'r') as f:
            return json.load(f)
    return []


@app.route("/upload_audio", methods=["POST"])
def upload_audio():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    filename = file.filename
    original_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(original_path)

    try:
        processed_path = standardize_audio(original_path)
        duration = check_audio_duration(processed_path)

        voice_id = str(uuid.uuid4())
        metadata = {
            "id": voice_id,
            "filename": os.path.basename(processed_path),
            "duration": duration,
            "upload_time": time.strftime('%Y-%m-%d %H:%M:%S'),
            "path": processed_path
        }
        save_metadata(metadata)
        return jsonify({"message": "上传成功", "id": voice_id}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/list_voices", methods=["GET"])
def list_voices():
    return jsonify(load_all_voices()), 200


@app.route("/submit_text_task", methods=["POST"])
def submit_text_task():
    data = request.get_json()
    text = data.get("text", "").strip()
    voice_id = data.get("voice_id")

    if not text or not voice_id:
        return jsonify({"error": "text 和 voice_id 不能为空"}), 400

    if len(text) < 800 or len(text) > 2000:
        return jsonify({"error": "文本长度应在800到2000字符之间"}), 400

    voices = load_all_voices()
    voice_exists = any(v["id"] == voice_id for v in voices)
    if not voice_exists:
        return jsonify({"error": "无效的 voice_id"}), 400

    task_id = str(uuid.uuid4())
    task_record = {
        "task_id": task_id,
        "voice_id": voice_id,
        "text": text,
        "submit_time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "status": "pending"
    }

    if os.path.exists(TEXT_TASK_PATH):
        with open(TEXT_TASK_PATH, 'r') as f:
            tasks = json.load(f)
    else:
        tasks = []

    tasks.append(task_record)
    with open(TEXT_TASK_PATH, 'w') as f:
        json.dump(tasks, f, indent=2)

    return jsonify({"message": "文本任务已提交", "task_id": task_id}), 200


@app.route("/generate_audio", methods=["POST"])
def generate_audio():
    data = request.get_json()
    task_id = data.get("task_id")

    if not task_id:
        return jsonify({"error": "缺少 task_id"}), 400

    if not os.path.exists(TEXT_TASK_PATH):
        return jsonify({"error": "任务列表为空"}), 400

    with open(TEXT_TASK_PATH, 'r') as f:
        tasks = json.load(f)

    task = next((t for t in tasks if t["task_id"] == task_id), None)
    if not task:
        return jsonify({"error": "未找到任务"}), 404

    text = task["text"]
    output_filename = f"{task_id}_output.wav"
    output_path = os.path.join(UPLOAD_FOLDER, output_filename)

    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.save_to_file(text, output_path)
        engine.runAndWait()

        task["status"] = "completed"
        task["output_audio"] = output_filename

        with open(TEXT_TASK_PATH, 'w') as f:
            json.dump(tasks, f, indent=2)

        return jsonify({
            "message": "音频生成成功",
            "audio_file": output_filename,
            "download_url": f"/get_audio/{task_id}"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/get_audio/<task_id>", methods=["GET"])
def get_audio(task_id):
    if not os.path.exists(TEXT_TASK_PATH):
        return jsonify({"error": "任务记录不存在"}), 404

    with open(TEXT_TASK_PATH, 'r') as f:
        tasks = json.load(f)

    task = next((t for t in tasks if t["task_id"] == task_id), None)
    if not task or task.get("status") != "completed":
        return jsonify({"error": "任务未完成或未找到"}), 404

    filename = task.get("output_audio")
    if not filename or not os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
        return jsonify({"error": "音频文件不存在"}), 404

    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


@app.route("/list_text_tasks", methods=["GET"])
def list_text_tasks():
    if not os.path.exists(TEXT_TASK_PATH):
        return jsonify([]), 200

    with open(TEXT_TASK_PATH, 'r') as f:
        tasks = json.load(f)
    return jsonify(tasks), 200


@app.route("/delete_task/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    if not os.path.exists(TEXT_TASK_PATH):
        return jsonify({"error": "任务列表不存在"}), 404

    with open(TEXT_TASK_PATH, 'r') as f:
        tasks = json.load(f)

    new_tasks = [t for t in tasks if t["task_id"] != task_id]

    for t in tasks:
        if t["task_id"] == task_id and t.get("output_audio"):
            path = os.path.join(UPLOAD_FOLDER, t["output_audio"])
            if os.path.exists(path):
                os.remove(path)

    with open(TEXT_TASK_PATH, 'w') as f:
        json.dump(new_tasks, f, indent=2)

    return jsonify({"message": f"任务 {task_id} 已删除"}), 200


@app.route("/upload_ppt", methods=["POST"])
def upload_ppt():
    if 'file' not in request.files:
        return jsonify({"error": "没有上传文件"}), 400

    file = request.files['file']
    filename = file.filename

    if not filename.lower().endswith('.pptx'):
        return jsonify({"error": "只支持 .pptx 文件"}), 400

    ppt_id = str(uuid.uuid4())
    save_path = os.path.join(PPT_FOLDER, f"{ppt_id}.pptx")
    file.save(save_path)

    try:
        prs = Presentation(save_path)
        slide_texts = []
        for slide in prs.slides:
            content = []
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    content.append(shape.text)
            slide_texts.append('\n'.join(content).strip())

        return jsonify({
            "ppt_id": ppt_id,
            "slides": slide_texts,
            "slide_count": len(slide_texts)
        }), 200

    except Exception as e:
        return jsonify({"error": f"PPT解析失败: {str(e)}"}), 500


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
