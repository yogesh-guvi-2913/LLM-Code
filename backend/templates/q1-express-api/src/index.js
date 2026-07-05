const express = require('express');
const cors = require('cors');

const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());

let items = [];

app.get('/api/items', (req, res) => {
  res.json(items);
});

app.post('/api/items', (req, res) => {
  // TODO: Implement create item
  res.status(201).json({ message: 'Not implemented' });
});

app.get('/api/items/:id', (req, res) => {
  // TODO: Implement get item by id
  res.status(404).json({ message: 'Not implemented' });
});

app.put('/api/items/:id', (req, res) => {
  // TODO: Implement update item
  res.status(404).json({ message: 'Not implemented' });
});

app.delete('/api/items/:id', (req, res) => {
  // TODO: Implement delete item
  res.status(404).json({ message: 'Not implemented' });
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});