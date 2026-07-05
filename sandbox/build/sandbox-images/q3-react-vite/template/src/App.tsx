// src/App.tsx — CANDIDATE EDITS THIS FILE.
//
// Task: finish this Todo list app. Right now the heading and input render, but:
//   - the "Add" button does nothing, and
//   - the list of todos is never rendered (stub below).
//
// Implement the following so the tests pass:
//   1. Clicking "Add" (or pressing Enter in the input) adds the typed text as a
//      new todo, then clears the input.
//   2. Render every todo as a list item inside the element with
//      data-testid="todo-list", in the order they were added. Give each item
//      data-testid="todo-item".
//   3. Clicking a todo toggles its completed state. A completed item must expose
//      data-state="completed" (and "active" when not completed).
//
// Only this file is reset to its starter state when a new session claims the box.
import { useState } from 'react';

type Todo = { id: number; text: string; completed: boolean };

export default function App() {
  const [text, setText] = useState('');
  // TODO: hold the list of todos in state.

  // TODO: implement adding a todo (button click + Enter key).

  return (
    <main className="app">
      <h1>Todo</h1>

      <div className="add-row">
        <input
          aria-label="new todo"
          placeholder="What needs doing?"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        {/* TODO: make this button add the todo. */}
        <button type="button">Add</button>
      </div>

      {/* TODO: render the todo list inside an element with
          data-testid="todo-list". */}
    </main>
  );
}
