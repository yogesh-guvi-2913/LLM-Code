// harness/solution/App.tsx — REFERENCE FULL SOLUTION. Not shipped to candidates.
// Dropping this in as /app/src/App.tsx makes the suite score 100/100.
import { useState } from 'react';

type Todo = { id: number; text: string; completed: boolean };

export default function App() {
  const [text, setText] = useState('');
  const [todos, setTodos] = useState<Todo[]>([]);

  function add() {
    const value = text.trim();
    if (!value) return;
    setTodos((prev) => [...prev, { id: Date.now() + prev.length, text: value, completed: false }]);
    setText('');
  }

  function toggle(id: number) {
    setTodos((prev) =>
      prev.map((t) => (t.id === id ? { ...t, completed: !t.completed } : t)),
    );
  }

  return (
    <main className="app">
      <h1>Todo</h1>

      <div className="add-row">
        <input
          aria-label="new todo"
          placeholder="What needs doing?"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') add();
          }}
        />
        <button type="button" onClick={add}>
          Add
        </button>
      </div>

      <ul data-testid="todo-list">
        {todos.map((t) => (
          <li
            key={t.id}
            data-testid="todo-item"
            data-state={t.completed ? 'completed' : 'active'}
            onClick={() => toggle(t.id)}
          >
            {t.text}
          </li>
        ))}
      </ul>
    </main>
  );
}
