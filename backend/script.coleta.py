import sqlite3

conn = sqlite3.connect('dados_imagem.db')
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS dados_imagem (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT,
  idade INTEGER,
  documento TEXT
)
''')

dados = [
    ("Isabella Souza", 28, "123.456.789-00"),
    ("Roberto Feresin", 21, "987.654.321-00"),
    ("Carlos Silva", 35, "111.222.333-44"),
    ("Habbibd Hammud", 32, "111.222.333-55")
]

c.executemany("INSERT INTO dados_imagem (nome, idade, documento) VALUES (?, ?, ?)", dados)
conn.commit()
conn.close()
