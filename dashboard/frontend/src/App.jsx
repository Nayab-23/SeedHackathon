import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import Lists from './pages/Lists';
import Profiles from './pages/Profiles';
import QueryLog from './pages/QueryLog';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="lists" element={<Lists />} />
        <Route path="profiles" element={<Profiles />} />
        <Route path="queries" element={<QueryLog />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
