import { CalendarPlus, Check, Clock, Plus, X } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';
import { Badge, Button, Card, Empty, Field, Input, Notice, PageHeader, Select } from '../components/ui';
import { api, formatDate } from '../lib/api';
import type { Appointment, AppointmentStatus, Customer } from '../types';

const statuses: AppointmentStatus[] = ['PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW'];
const tone = (s: AppointmentStatus) =>
  s === 'CONFIRMED' || s === 'COMPLETED' ? 'green' : s === 'PENDING' ? 'amber' : s === 'CANCELLED' ? 'red' : 'neutral';

type BusinessHour = { dayOfWeek: string; opensAt: string; closesAt: string };

export function AppointmentsPage() {
  const [items, setItems] = useState<Appointment[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [hours, setHours] = useState<BusinessHour[]>([]);
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('');
  const [form, setForm] = useState({ customerId: '', scheduledStart: '' });
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [saving, setSaving] = useState(false);

  const load = () =>
    api<{ appointments: Appointment[] }>(`/appointments?limit=100${filter ? `&status=${filter}` : ''}`).then((r) =>
      setItems(r.appointments)
    );

  useEffect(() => {
    void load();
  }, [filter]);

  useEffect(() => {
    api<{ customers: Customer[] }>('/customers?limit=100').then((r) => setCustomers(r.customers));
    api<{ hours: BusinessHour[] }>('/business/hours')
      .then((r) => setHours(r.hours))
      .catch(() => {});
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      if (!form.scheduledStart) {
        setError('Please choose an appointment date and time.');
        return;
      }
      const startIso = new Date(form.scheduledStart).toISOString();
      await api('/appointments', {
        method: 'POST',
        body: JSON.stringify({
          customerId: form.customerId,
          scheduledStart: startIso,
        }),
      });
      setOpen(false);
      setForm({ customerId: '', scheduledStart: '' });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to schedule appointment.');
    } finally {
      setSaving(false);
    }
  };

  const update = async (id: string, status: AppointmentStatus) => {
    setActionError('');
    try {
      await api(`/appointments/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) });
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update appointment.');
    }
  };

  return (
    <>
      <PageHeader
        title="Appointments"
        description="Review, schedule, and manage website customer appointments."
        action={
          <Button
            onClick={() => {
              setOpen(!open);
              setError('');
            }}
          >
            {open ? <X size={17} /> : <Plus size={17} />} {open ? 'Close' : 'New appointment'}
          </Button>
        }
      />
      {open && (
        <Card className="inline-create">
          <form onSubmit={submit}>
            {error && <Notice kind="error">{error}</Notice>}
            {hours.length > 0 ? (
              <div className="hours-banner">
                <strong>Operating hours:</strong>{' '}
                {hours
                  .map((h) => `${h.dayOfWeek.slice(0, 3)}: ${h.opensAt.slice(0, 5)}–${h.closesAt.slice(0, 5)}`)
                  .join(', ')}
              </div>
            ) : (
              <Notice kind="info">
                No weekly hours have been configured yet. Appointments cannot be scheduled outside operating hours.
              </Notice>
            )}
            <div className="form-grid">
              <Field label="Customer">
                <Select
                  value={form.customerId}
                  onChange={(e) => setForm({ ...form, customerId: e.target.value })}
                  required
                >
                  <option value="">Select customer</option>
                  {customers.map((c) => (
                    <option value={c.id} key={c.id}>
                      {c.name || c.email || c.phone || 'Unnamed customer'}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Start time">
                <Input
                  type="datetime-local"
                  value={form.scheduledStart}
                  onChange={(e) => setForm({ ...form, scheduledStart: e.target.value })}
                  required
                />
              </Field>
            </div>
            <Button disabled={saving}>
              <CalendarPlus size={17} />
              {saving ? 'Scheduling...' : 'Create appointment'}
            </Button>
          </form>
        </Card>
      )}
      {actionError && <Notice kind="error">{actionError}</Notice>}
      <Card>
        <div className="table-toolbar">
          <div>
            <h2>Booking schedule</h2>
            <p>{items.length} appointments shown</p>
          </div>
          <Select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">All statuses</option>
            {statuses.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </Select>
        </div>
        {items.length ? (
          <div className="data-table appointments-table">
            <div className="table-row table-head">
              <span>Customer</span>
              <span>Schedule</span>
              <span>Status</span>
              <span>Actions</span>
            </div>
            {items.map((item) => (
              <div className="table-row" key={item.id}>
                <span>
                  <strong>{item.customerName || 'Unnamed customer'}</strong>
                  <small>{item.customerEmail || item.customerPhone || 'No contact snapshot'}</small>
                </span>
                <span>
                  <strong>{formatDate(item.scheduledStart)}</strong>
                  <small>
                    to{' '}
                    {new Date(item.scheduledEnd).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </small>
                </span>
                <span>
                  <Badge tone={tone(item.status)}>{item.status}</Badge>
                </span>
                <span className="row-actions">
                  {item.status === 'PENDING' && (
                    <button title="Confirm appointment" onClick={() => void update(item.id, 'CONFIRMED')}>
                      <Check size={17} />
                    </button>
                  )}
                  {['PENDING', 'CONFIRMED'].includes(item.status) && (
                    <button title="Cancel appointment" onClick={() => void update(item.id, 'CANCELLED')}>
                      <X size={17} />
                    </button>
                  )}
                  {item.status === 'CONFIRMED' && (
                    <button title="Mark completed" onClick={() => void update(item.id, 'COMPLETED')}>
                      <Clock size={17} />
                    </button>
                  )}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <Empty title="No appointments found" text="Create a booking or change your filter." />
        )}
      </Card>
    </>
  );
}
