// server.js is fixed scaffolding (not editable by the candidate, not reset on
// claim). It mounts the candidate's router from ./src/todos.js. Candidates
// implement the routes in src/todos.js only.
const express = require('express');
const makeRouter = require('./src/todos');

const app = express();
app.use(express.json());
app.use('/todos', makeRouter());

app.get('/health', (_req, res) => res.json({ ok: true }));

const port = process.env.PORT || 3000;
app.listen(port, '0.0.0.0', () => console.log(`todo api listening on ${port}`));
