import { HashRouter, Navigate, Routes, Route } from 'react-router-dom';
import AppShell from './components/AppShell';
import EntryLayout from './components/EntryLayout';

import Home from './pages/Home';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Live from './pages/Live';
import Ppe from './pages/Ppe';
import Workers from './pages/Workers';
import WorkerProfile from './pages/WorkerProfile';
import Attendance from './pages/Attendance';
import Alerts from './pages/Alerts';
import Reports from './pages/Reports';
import Insights from './pages/Insights';
import Devices from './pages/Devices';
import DevicesSync from './pages/DevicesSync';
import Audit from './pages/Audit';
import Champions from './pages/Champions';
import Settings from './pages/Settings';
import SettingsPpe from './pages/SettingsPpe';
import SettingsUsers from './pages/SettingsUsers';
import Biometric from './pages/Biometric';
import ScanPpe from './pages/ScanPpe';
import ComplianceCheck from './pages/ComplianceCheck';

function Shelled(Page) {
  return (
    <AppShell>
      <Page />
    </AppShell>
  );
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/entry" element={<EntryLayout />}>
          <Route index element={<Navigate to="biometric" replace />} />
          <Route path="biometric" element={<Biometric />} />
          <Route path="scan-ppe" element={<ScanPpe />} />
          <Route path="compliance" element={<ComplianceCheck />} />
        </Route>

        <Route path="/dashboard" element={Shelled(Dashboard)} />
        <Route path="/live" element={Shelled(Live)} />
        <Route path="/ppe" element={Shelled(Ppe)} />
        <Route path="/workers" element={Shelled(Workers)} />
        <Route path="/workers/:id" element={Shelled(WorkerProfile)} />
        <Route path="/attendance" element={Shelled(Attendance)} />
        <Route path="/alerts" element={Shelled(Alerts)} />
        <Route path="/reports" element={Shelled(Reports)} />
        <Route path="/insights" element={Shelled(Insights)} />
        <Route path="/devices" element={Shelled(Devices)} />
        <Route path="/devices/sync" element={Shelled(DevicesSync)} />
        <Route path="/audit" element={Shelled(Audit)} />
        <Route path="/champions" element={Shelled(Champions)} />
        <Route path="/settings" element={Shelled(Settings)} />
        <Route path="/settings/ppe" element={Shelled(SettingsPpe)} />
        <Route path="/settings/users" element={Shelled(SettingsUsers)} />

        <Route path="*" element={<Home />} />
      </Routes>
    </HashRouter>
  );
}
