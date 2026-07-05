// App.test.tsx — grades the candidate's /app/src/App.tsx.
//
// Test titles are load-bearing: harness/score.js maps each title to a weight,
// so do NOT rename them without updating score.js. Weights sum to 100.
//
// The candidate component is imported via the `@app` alias (see vite.config.ts),
// which resolves to /app/src in the container.
import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '@app/App';

async function addTodo(user: ReturnType<typeof userEvent.setup>, text: string) {
  const input = screen.getByLabelText('new todo') as HTMLInputElement;
  await user.click(input);
  await user.type(input, text);
  await user.click(screen.getByRole('button', { name: /add/i }));
}

describe('Todo app', () => {
  it('adds a todo when Add is clicked [weight:30]', async () => {
    const user = userEvent.setup();
    render(<App />);

    await addTodo(user, 'buy milk');

    const list = await screen.findByTestId('todo-list');
    expect(within(list).getByText('buy milk')).toBeInTheDocument();
  });

  it('renders multiple todos in order [weight:35]', async () => {
    const user = userEvent.setup();
    render(<App />);

    await addTodo(user, 'first');
    await addTodo(user, 'second');
    await addTodo(user, 'third');

    const list = await screen.findByTestId('todo-list');
    const items = within(list).getAllByTestId('todo-item');
    expect(items).toHaveLength(3);
    expect(items.map((el) => el.textContent)).toEqual(['first', 'second', 'third']);
  });

  it('toggles completed state on click [weight:35]', async () => {
    const user = userEvent.setup();
    render(<App />);

    await addTodo(user, 'walk dog');

    const list = await screen.findByTestId('todo-list');
    const item = within(list).getByTestId('todo-item');

    expect(item).toHaveAttribute('data-state', 'active');
    await user.click(item);
    expect(item).toHaveAttribute('data-state', 'completed');
    await user.click(item);
    expect(item).toHaveAttribute('data-state', 'active');
  });
});
