const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const cors = require('cors');

const app = express();
app.use(cors());

const db = new sqlite3.Database('./dados_imagem.db');

app.get('/dados', (req, res) => {
  db.all("SELECT * FROM dados_imagem", [], (err, rows) => {
    if (err) {
      console.error(err.message);
      return res.status(500).json({ error: err.message });
    }
    res.json(rows);
  });
});

app.listen(3001, () => {
  console.log('API ouvindo em http://localhost:3001');
});
