# server.py is fixed scaffolding (not editable by the candidate, not reset on
# claim). It mounts the candidate's blueprint from src/todos.py. Candidates
# implement the routes in src/todos.py only.
import os
from flask import Flask
from src.todos import make_blueprint

app = Flask(__name__)
app.register_blueprint(make_blueprint(), url_prefix="/todos")


@app.get("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "3000")))
