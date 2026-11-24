from flask import Flask, jsonify, request
from parser.templates import TemplateStore
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
store = TemplateStore()


@app.route("/health", methods=["GET"])
def get_health():
    return jsonify({"status": "ok"})  # status code 200 is default


@app.route("/parse", methods=["POST"])
def post_parse():
    request_body = request.get_json(silent=True)

    if request_body is None:
        return jsonify({"error": "invalid JSON"}), 400

    if isinstance(request_body, dict) and "lines" in request_body and isinstance(request_body["lines"], list):
        lines = request_body["lines"]
        for i, entry in enumerate(lines):
            if not isinstance(entry, dict):
                msg = f"lines[{i}]: entry must be an object"
                return jsonify({"error": msg}), 400
            source = entry.get("source")
            text = entry.get("text")
            if not isinstance(source, str) or not source.strip():
                msg = f"lines[{i}]: 'source' must be a non-empty string"
                return jsonify({"error": msg}), 400
            if not isinstance(text, str):
                msg = f"lines[{i}]: 'text' must be a string"
                return jsonify({"error": msg}), 400

        templates = store.parse_lines(lines)
        return jsonify({"templates": templates})

    else:
        return jsonify({"error": "'lines' must be a list"}), 400


@app.errorhandler(HTTPException)
def handle_http_execptions(e):
    return jsonify({"error": e.description}), e.code


@app.errorhandler(Exception)
def handle_execptions(e):
    return jsonify({"error": str(e)}), 500
