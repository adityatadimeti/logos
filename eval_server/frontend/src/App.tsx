import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './components/Dashboard';
import TraceView from './components/TraceView';
import AgentGraph from './components/AgentGraph';

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/trace/:traceId" element={<TraceView />} />
        <Route path="/agent-graph" element={<AgentGraph />} />
      </Routes>
    </Layout>
  );
}

export default App;
