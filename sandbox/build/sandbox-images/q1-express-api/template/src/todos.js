// src/todos.js — CANDIDATE EDITS THIS FILE.
//
// Task: implement a small in-memory Todo REST API on this router.
//   GET    /todos        -> 200, JSON array of todos                (done for you)
//   POST   /todos        -> 201, creates { id, title, done:false }  (TODO)
//   GET    /todos/:id     -> 200 todo, or 404 if missing            (TODO)
//
// Only this file is reset to its starter state when a new session claims the box.
const express = require('express');

module.exports = function makeRouter() {
  const router = express.Router();
  const todos = [];
  let nextId = 1;

  // Implemented for you.
  router.get('/', (_req, res) => {
    res.status(200).json(todos);
  });

  // TODO: implement POST /todos
  // TODO: implement GET /todos/:id

  return router;
};
