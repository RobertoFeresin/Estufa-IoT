import React, { useEffect, useState } from 'react';
import axios from 'axios';

function App() {
  const [dados, setDados] = useState([]);

  useEffect(() => {
    axios.get('http://localhost:3001/dados')
      .then(response => setDados(response.data))
      .catch(err => console.error(err));
  }, []);

  return (
    <div style={{ padding: '2rem' }}>
      <h1>Consulta de Dados da Imagem</h1>
      <table border="1" cellPadding="10">
        <thead>
          <tr>
            <th>ID</th>
            <th>Nome</th>
            <th>Idade</th>
            <th>Documento</th>
          </tr>
        </thead>
        <tbody>
          {dados.map(d => (
            <tr key={d.id}>
              <td>{d.id}</td>
              <td>{d.nome}</td>
              <td>{d.idade}</td>
              <td>{d.documento}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;
