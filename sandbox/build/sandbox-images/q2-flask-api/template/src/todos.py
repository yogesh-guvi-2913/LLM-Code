# src/todos.py — CANDIDATE EDITS THIS FILE.
#
# Task: implement a small in-memory Todo REST API on this blueprint.
#   GET    /todos        -> 200, JSON array of todos                (done for you)
#   POST   /todos        -> 201, creates { id, title, done: false } (TODO)
#   GET    /todos/<id>    -> 200 todo, or 404 if missing            (TODO)
#
# Only this file is reset to its starter state when a new session claims the box.
from flask import Blueprint, jsonify


def make_blueprint():
    bp = Blueprint("todos", __name__)
    todos = []
    state = {"next_id": 1}

    # Implemented for you.
    @bp.route("", methods=["GET"])
    def list_todos():
        return jsonify(todos), 200

    # TODO: implement POST "" -> 201 {id, title, done: false}
    # TODO: implement GET "/<int:tid>" -> 200 todo or 404

    return bp
