import { CalendarPlus, Check, Clock, Plus, X } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';
import { Badge, Button, Card, Empty, Field, Input, PageHeader, Select } from '../components/ui';
import { api, formatDate } from '../lib/api';
import type { Appointment, AppointmentStatus, Customer } from '../types';

const statuses: AppointmentStatus[] = ['PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW'];
const tone = (s: AppointmentStatus) =>
  s === 'CONFIRMED' || s === 'COMPLETED' ? 'green' : s === 'PENDING' ? 'amber' : s === 'CANCELLED' ? 'red' : 'neutral';

export function AppointmentsPage() {
  const [items, setItems] = useState<Appointment[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('');
  const [form, setForm] = useState({ customerId: '', scheduledStart: '' });

  const load = () =>
    api<{ appointments: Appointment[] }>(`/appointments?limit=100${filter ? `&status=${filter}` : ''}`).then((r) =>
      setItems(r.appointments)
    );

  useEffect(() => {
    void load();
  }, [filter]);

  useEffect(() => {
    api<{ customers: Customer[] }>('/customers?limit=100').then((r) => setCustomers(r.customers));
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    await api('/appointments', {
      method: 'POST',
      body: JSON.stringify({
        customerId: form.customerId,
        scheduledStart: new Date(form.scheduledStart).toISOString(),
      }),
    });
    setOpen(false);
    setForm({ customerId: '', scheduledStart: '' });
    await load();
  };

  const update = async (id: string, status: AppointmentStatus) => {
    await api(`/appointments/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) });
    await load();
  };

  return (
    <>
      <PageHeader
        title="Appointments"
        description="Review, schedule, and manage website customer appointments."
        action={
          <Button onClick={() => setOpen(!open)}>
            {open ? <X size={17} /> : <Plus size={17} />} {open ? 'Close' : 'New appointment'}
          </Button>
        }
      />
      {open && (
        <Card className="inline-create">
          <form onSubmit={submit}>
            <div className="form-grid">
              <Field label="Customer">
                <Select value={form.customerId} onChange={(e) => setForm({ ...form, customerId: e.target.value })} required>
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
            <Button>
              <CalendarPlus size={17} />
              Create appointment
            </Button>
          </form>
        </Card>
      )}
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
          <div className="data-table">
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
                  <small>to {new Date(item.scheduledEnd).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</small>
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
