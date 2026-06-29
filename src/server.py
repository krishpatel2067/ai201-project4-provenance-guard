from flask import Flask, jsonify

from db import init_db
from log import init_log_file

from routes.appeals import appeals_bp
from routes.content import content_bp
from routes.creators import creators_bp

app = Flask(__name__)

# Wire routes
app.register_blueprint(appeals_bp)
app.register_blueprint(content_bp)
app.register_blueprint(creators_bp)
# [TODO] get logs endpoint

# 404 catchall
@app.errorhandler(404)
def api_not_found(e):
    return jsonify(error="Resource not found"), 404

# Entry point

if __name__ == "__main__":
    import os

    os.makedirs("data", exist_ok=True)
    init_log_file()
    init_db()
    app.run(debug=True)
