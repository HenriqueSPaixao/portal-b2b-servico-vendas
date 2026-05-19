import { BrowserRouter, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout.jsx';
import ProcessosList from './components/ProcessosList.jsx';
import ProcessoDetalhe from './components/ProcessoDetalhe.jsx';

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<ProcessosList />} />
          <Route path="/processos/:id" element={<ProcessoDetalhe />} />
          <Route path="*" element={<ProcessosList />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
