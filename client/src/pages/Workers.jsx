import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Pencil, Plus, Search, Trash2, X } from 'lucide-react';
import { PageHeader, Badge, Button } from '../components/ui';
import {
  createWorker,
  deleteWorker,
  listWorkerDepartments,
  listWorkers,
  updateWorker,
} from '../services/workers';

const FILTERS = ['ALL', 'UNDERGROUND', 'SURFACE', 'HIGH RISK', 'NON-COMPLIANT'];
const EMPTY_FORM = {
  employee_code: '',
  name: '',
  department_id: '',
  designation: '',
  phone: '',
  email: '',
  rfid_uid: '',
  status: 'ACTIVE',
};

export default function Workers() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('ALL');
  const [workers, setWorkers] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  useEffect(() => {
    loadWorkers();
  }, []);

  async function loadWorkers() {
    setLoading(true);
    setError('');
    try {
      const [workerRows, departmentRows] = await Promise.all([listWorkers(), listWorkerDepartments()]);
      setWorkers(workerRows);
      setDepartments(departmentRows);
    } catch (err) {
      setError(err.message || 'Unable to load workers.');
    } finally {
      setLoading(false);
    }
  }

  const rows = useMemo(() => {
    return workers.filter((w) => {
      const q = query.toLowerCase();
      const matchesQuery = !q || w.name.toLowerCase().includes(q) || w.id.toLowerCase().includes(q) || w.rfidId.toLowerCase().includes(q);
      const matchesFilter =
        filter === 'ALL' ||
        (filter === 'HIGH RISK' && w.risk === 'HIGH') ||
        (filter === 'NON-COMPLIANT' && w.ppeScore < 90) ||
        (filter === 'UNDERGROUND' && ['Underground Mining', 'Mining'].includes(w.department)) ||
        (filter === 'SURFACE' && !['Underground Mining', 'Mining'].includes(w.department));
      return matchesQuery && matchesFilter;
    });
  }, [workers, query, filter]);

  function openCreate() {
    setForm({ ...EMPTY_FORM, department_id: departments[0]?.department_id || '' });
    setModal({ mode: 'create', worker: null });
    setError('');
  }

  function openEdit(worker) {
    setForm({
      employee_code: worker.employee_code,
      name: worker.name,
      department_id: worker.department_id,
      designation: worker.designation || '',
      phone: worker.phone || '',
      email: worker.email || '',
      rfid_uid: worker.rfid_uid || '',
      status: worker.status,
    });
    setModal({ mode: 'edit', worker });
    setError('');
  }

  function closeModal() {
    setModal(null);
    setForm(EMPTY_FORM);
    setSaving(false);
  }

  function setField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function buildPayload() {
    return {
      employee_code: form.employee_code.trim(),
      name: form.name.trim(),
      department_id: Number(form.department_id),
      designation: form.designation.trim() || null,
      phone: form.phone.trim() || null,
      email: form.email.trim() || null,
      rfid_uid: form.rfid_uid.trim() || null,
      status: form.status,
    };
  }

  async function submitWorker(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const payload = buildPayload();
      if (modal.mode === 'create') {
        const created = await createWorker(payload);
        setWorkers((prev) => [created, ...prev]);
      } else {
        const updated = await updateWorker(modal.worker.worker_id, payload);
        setWorkers((prev) => prev.map((w) => (w.worker_id === updated.worker_id ? updated : w)));
      }
      closeModal();
    } catch (err) {
      setError(err.message || 'Unable to save worker.');
      setSaving(false);
    }
  }

  function handleDelete(worker) {
    setDeleteConfirm(worker);
  }

  async function confirmDelete() {
    if (!deleteConfirm) return;
    const worker = deleteConfirm;
    setDeleteConfirm(null);
    setError('');
    try {
      await deleteWorker(worker.worker_id);
      setWorkers((prev) => prev.map((w) => (w.worker_id === worker.worker_id ? { ...w, status: 'INACTIVE' } : w)));
    } catch (err) {
      setError(err.message || 'Unable to delete worker.');
    }
  }

  return (
    <div className="animate-fadeUp">
      <PageHeader
        eyebrow={`${workers.length} RECORDS`}
        title="Workers"
        subtitle="Worker safety and PPE compliance records."
        right={<Button onClick={openCreate}><Plus size={13} /> ADD WORKER</Button>}
      />

      {error && (
        <div className="panel border-danger/40 text-danger text-xs px-4 py-3 mb-4">
          {error}
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <div className="relative flex-1 max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-textMuted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name / Worker ID / RFID"
            className="w-full bg-input border border-border rounded-md pl-9 pr-3 py-2 text-xs focus-ring"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`label-op !text-[0.62rem] px-3 py-2 rounded-md border transition-colors ${filter === f ? 'border-safety text-safety bg-safetySubtle' : 'border-border text-textSecondary hover:text-text'
                }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                {['Worker', 'ID', 'Department', 'Shift', 'PPE Score', 'Risk', 'Status', 'Actions'].map((h) => (
                  <th key={h} className="label-op text-left px-4 py-3 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-textMuted">Loading workers...</td></tr>
              )}
              {rows.map((w) => (
                <tr
                  key={w.worker_id}
                  onClick={() => navigate(`/workers/${w.id}`)}
                  className="border-b border-border/50 last:border-0 hover:bg-elevated/60 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 font-semibold whitespace-nowrap">{w.name}</td>
                  <td className="px-4 py-3 mono text-textSecondary whitespace-nowrap">{w.id}</td>
                  <td className="px-4 py-3 text-textSecondary whitespace-nowrap">{w.department}</td>
                  <td className="px-4 py-3 text-textSecondary">{w.shift}</td>
                  <td className="px-4 py-3 mono font-semibold whitespace-nowrap">{w.ppeScore}%</td>
                  <td className="px-4 py-3">
                    <Badge tone={w.risk === 'HIGH' ? 'danger' : w.risk === 'MEDIUM' ? 'warning' : 'safety'}>{w.risk}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={w.status === 'ACTIVE' ? 'safety' : 'default'}>{w.status}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); openEdit(w); }}
                        className="p-1.5 rounded-md border border-border text-textSecondary hover:text-safety hover:border-safety/50 focus-ring"
                        aria-label={`Edit ${w.name}`}
                      >
                        <Pencil size={12} />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(w); }}
                        className="p-1.5 rounded-md border border-danger/40 text-danger hover:bg-danger/10 focus-ring"
                        aria-label={`Delete ${w.name}`}
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-textMuted">No workers match this search.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {modal && (
        <div className="fixed inset-0 z-50 bg-bg/80 backdrop-blur flex items-center justify-center px-4">
          <form onSubmit={submitWorker} className="panel-elevated w-full max-w-2xl p-5 animate-fadeUp">
            <div className="flex items-start justify-between gap-4 mb-5">
              <div>
                <div className="label-op text-safety mb-1">{modal.mode === 'create' ? 'NEW RECORD' : 'UPDATE RECORD'}</div>
                <h2 className="text-lg font-extrabold tracking-tight">{modal.mode === 'create' ? 'Add Worker' : 'Edit Worker'}</h2>
              </div>
              <button type="button" onClick={closeModal} className="p-1.5 text-textSecondary hover:text-text focus-ring rounded">
                <X size={18} />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Employee Code">
                <input required value={form.employee_code} onChange={(e) => setField('employee_code', e.target.value)} className="field" />
              </Field>
              <Field label="Worker Name">
                <input required value={form.name} onChange={(e) => setField('name', e.target.value)} className="field" />
              </Field>
              <Field label="Department">
                <select required value={form.department_id} onChange={(e) => setField('department_id', e.target.value)} className="field">
                  <option value="">Select department</option>
                  {departments.map((d) => <option key={d.department_id} value={d.department_id}>{d.name}</option>)}
                </select>
              </Field>
              <Field label="Designation">
                <input value={form.designation} onChange={(e) => setField('designation', e.target.value)} className="field" />
              </Field>
              <Field label="Phone">
                <input value={form.phone} onChange={(e) => setField('phone', e.target.value)} className="field" />
              </Field>
              <Field label="Email">
                <input type="email" value={form.email} onChange={(e) => setField('email', e.target.value)} className="field" />
              </Field>
              <Field label="RFID UID">
                <input value={form.rfid_uid} onChange={(e) => setField('rfid_uid', e.target.value)} className="field" />
              </Field>
              <Field label="Status">
                <select value={form.status} onChange={(e) => setField('status', e.target.value)} className="field">
                  <option>ACTIVE</option>
                  <option>INACTIVE</option>
                </select>
              </Field>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <Button type="button" variant="outline" onClick={closeModal}>CANCEL</Button>
              <Button type="submit" disabled={saving}>{saving ? 'SAVING...' : modal.mode === 'create' ? 'CREATE WORKER' : 'SAVE CHANGES'}</Button>
            </div>
          </form>
        </div>
      )}

      {deleteConfirm && (
        <div className="fixed inset-0 z-50 bg-bg/85 backdrop-blur-sm flex items-center justify-center px-4">
          <div className="panel-elevated w-full max-w-md p-6 animate-fadeUp relative overflow-hidden rock-texture">
            <div className="absolute top-0 left-0 w-full h-[2px] bg-danger"></div>
            <div className="flex items-start gap-4 mb-4">
              <div className="w-10 h-10 rounded-full bg-dangerSubtle border border-dangerBorder flex items-center justify-center text-danger shrink-0">
                <Trash2 size={16} />
              </div>
              <div>
                <h3 className="text-sm font-extrabold tracking-tight">Deactivate Worker Record</h3>
                <p className="text-xs text-textSecondary mt-2 leading-relaxed">
                  Are you sure you want to deactivate <span className="text-text font-semibold">{deleteConfirm.name}</span> ({deleteConfirm.id})? This will mark their status as inactive.
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <Button variant="outline" onClick={() => setDeleteConfirm(null)}>
                Cancel
              </Button>
              <Button variant="danger" onClick={confirmDelete}>
                Deactivate
              </Button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <div className="label-op mb-1.5">{label}</div>
      {children}
    </label>
  );
}
