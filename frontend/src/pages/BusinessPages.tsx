import { Save } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';
import { Button, Card, Field, Input, Notice, PageHeader } from '../components/ui';
import { api } from '../lib/api';

type Business = {
  name: string;
  address: string | null;
  city: string | null;
  stateProvince: string | null;
  postalCode: string | null;
  countryCode: string | null;
  industry: string | null;
  timezone: string;
  status?: string;
  id?: string;
  createdAt?: string;
  updatedAt?: string;
};

export function BusinessPage() {
  const [form, setForm] = useState<Business | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api<{ business: Business }>('/business')
      .then((r) => setForm(r.business))
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load business profile.'));
  }, []);

  if (!form) return null;

  const change = (key: keyof Business, value: string) => {
    setForm({ ...form, [key]: value.trim() === '' ? null : value });
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        address: form.address ? form.address.trim() : null,
        city: form.city ? form.city.trim() : null,
        stateProvince: form.stateProvince ? form.stateProvince.trim() : null,
        postalCode: form.postalCode ? form.postalCode.trim() : null,
        countryCode: form.countryCode ? form.countryCode.trim().toUpperCase() : null,
        industry: form.industry ? form.industry.trim() : null,
        timezone: form.timezone.trim(),
      };
      const r = await api<{ business: Business }>('/business', {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      setForm(r.business);
      setMessage('Business profile saved.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageHeader title="Business profile" description="Core information used across your workspace." />
      <Card className="form-card">
        <form onSubmit={submit}>
          {message && <Notice>{message}</Notice>}
          {error && <Notice kind="error">{error}</Notice>}
          <div className="form-grid">
            <Field label="Business name">
              <Input
                value={form.name}
                onChange={(e) => change('name', e.target.value)}
                required
              />
            </Field>
            <Field label="Industry">
              <Input
                value={form.industry ?? ''}
                onChange={(e) => change('industry', e.target.value)}
                placeholder="e.g. Retail, Wellness, Consulting"
              />
            </Field>
          </div>
          <Field label="Address">
            <Input
              value={form.address ?? ''}
              onChange={(e) => change('address', e.target.value)}
              placeholder="e.g. 123 Main Street"
            />
          </Field>
          <div className="form-grid thirds">
            <Field label="City">
              <Input
                value={form.city ?? ''}
                onChange={(e) => change('city', e.target.value)}
                placeholder="e.g. Lahore"
              />
            </Field>
            <Field label="State / province">
              <Input
                value={form.stateProvince ?? ''}
                onChange={(e) => change('stateProvince', e.target.value)}
                placeholder="e.g. Punjab"
              />
            </Field>
            <Field label="Postal code">
              <Input
                value={form.postalCode ?? ''}
                onChange={(e) => change('postalCode', e.target.value)}
                placeholder="e.g. 54000"
              />
            </Field>
          </div>
          <div className="form-grid">
            <Field label="Country code" hint="Two-letter ISO code, for example PK or US.">
              <Input
                value={form.countryCode ?? ''}
                maxLength={2}
                onChange={(e) => change('countryCode', e.target.value.toUpperCase())}
                placeholder="PK"
              />
            </Field>
            <Field label="Timezone" hint="Use an IANA timezone such as Asia/Karachi or UTC.">
              <Input
                value={form.timezone}
                onChange={(e) => change('timezone', e.target.value)}
                required
              />
            </Field>
          </div>
          <div className="form-actions">
            <Button disabled={saving}>
              <Save size={17} />
              {saving ? 'Saving...' : 'Save profile'}
            </Button>
          </div>
        </form>
      </Card>
    </>
  );
}

type Settings = {
  appointmentDurationMinutes: number;
  bookingWindowDays: number;
  maximumAppointmentsPerDay: number | null;
  allowCancellation: boolean;
  allowReschedule: boolean;
  collectPhone: boolean;
  collectEmail: boolean;
  confirmationRequired: boolean;
};

export function SettingsPage() {
  const [form, setForm] = useState<Settings | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api<{ settings: Settings }>('/business/settings')
      .then((r) => setForm(r.settings))
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load booking settings.'));
  }, []);

  if (!form) return null;

  const toggle = (key: keyof Settings) => setForm({ ...form, [key]: !form[key] });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setSaving(true);
    try {
      const payload = {
        appointmentDurationMinutes: Number(form.appointmentDurationMinutes),
        bookingWindowDays: Number(form.bookingWindowDays),
        maximumAppointmentsPerDay:
          form.maximumAppointmentsPerDay && Number(form.maximumAppointmentsPerDay) > 0
            ? Number(form.maximumAppointmentsPerDay)
            : null,
        allowCancellation: Boolean(form.allowCancellation),
        allowReschedule: Boolean(form.allowReschedule),
        collectPhone: Boolean(form.collectPhone),
        collectEmail: Boolean(form.collectEmail),
        confirmationRequired: Boolean(form.confirmationRequired),
      };
      const r = await api<{ settings: Settings }>('/business/settings', {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      setForm(r.settings);
      setMessage('Booking settings saved.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed.');
    } finally {
      setSaving(false);
    }
  };

  const toggles: [keyof Settings, string, string][] = [
    ['allowCancellation', 'Allow cancellation', 'Customers can cancel eligible bookings.'],
    ['allowReschedule', 'Allow rescheduling', 'Customers can move eligible bookings.'],
    ['confirmationRequired', 'Require confirmation', 'New bookings start pending confirmation.'],
    ['collectPhone', 'Collect phone number', 'Ask for a phone identity while booking.'],
    ['collectEmail', 'Collect email address', 'Ask for an email identity while booking.'],
  ];

  return (
    <>
      <PageHeader title="Booking settings" description="Simple rules that shape every new appointment." />
      <form onSubmit={submit}>
        <Card className="form-card">
          <h2>Booking rules</h2>
          {message && <Notice>{message}</Notice>}
          {error && <Notice kind="error">{error}</Notice>}
          <div className="form-grid thirds">
            <Field label="Appointment duration (minutes)">
              <Input
                type="number"
                min="1"
                max="1440"
                value={form.appointmentDurationMinutes}
                onChange={(e) => setForm({ ...form, appointmentDurationMinutes: +e.target.value })}
                required
              />
            </Field>
            <Field label="Booking window (days)">
              <Input
                type="number"
                min="1"
                max="3650"
                value={form.bookingWindowDays}
                onChange={(e) => setForm({ ...form, bookingWindowDays: +e.target.value })}
                required
              />
            </Field>
            <Field label="Maximum per day" hint="Leave empty for no daily cap.">
              <Input
                type="number"
                min="1"
                value={form.maximumAppointmentsPerDay ?? ''}
                onChange={(e) =>
                  setForm({
                    ...form,
                    maximumAppointmentsPerDay: e.target.value ? +e.target.value : null,
                  })
                }
                placeholder="No cap"
              />
            </Field>
          </div>
          <div className="toggle-list">
            {toggles.map(([key, label, text]) => (
              <label className="toggle-row" key={key}>
                <div>
                  <strong>{label}</strong>
                  <small>{text}</small>
                </div>
                <input
                  type="checkbox"
                  checked={form[key] as boolean}
                  onChange={() => toggle(key)}
                />
                <span className="toggle" />
              </label>
            ))}
          </div>
          <div className="form-actions">
            <Button disabled={saving}>
              <Save size={17} />
              {saving ? 'Saving...' : 'Save settings'}
            </Button>
          </div>
        </Card>
      </form>
    </>
  );
}
