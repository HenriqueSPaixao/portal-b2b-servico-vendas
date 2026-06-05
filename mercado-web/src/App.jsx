import Layout from './components/Layout.jsx';
import PropostasPanel from './components/PropostasPanel.jsx';
import ProcessosTable from './components/ProcessosTable.jsx';
import SnapshotPanel from './components/SnapshotPanel.jsx';

export default function App() {
  return (
    <Layout>
      <div className="space-y-5">
        <PropostasPanel />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <ProcessosTable />
          <SnapshotPanel />
        </div>
      </div>
    </Layout>
  );
}
