import { Mail, Phone, Plus, Search, Trash2, UserPlus, X } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';
import { Badge, Button, Card, Empty, Field, Input, PageHeader } from '../components/ui';
import { api, formatDate } from '../lib/api';
import type { Customer } from '../types';

export function CustomersPage() {
  const [items, setItems] = useState<Customer[]>([]);
  const [search, setSearch] = useState('');
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: '', phone: '', email: '' });

  const load = () =>
    api<{ customers: Customer[] }>(`/customers?limit=100&search=${encodeURIComponent(search)}`).then((r) =>
      setItems(r.customers)
    );

  useEffect(() => {
    const timer = setTimeout(() => void load(), 250);
    return () => clearTimeout(timer);
  }, [search]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    await api('/customers', {
      method: 'POST',
      body: JSON.stringify({
        name: form.name.trim() || null,
        phone: form.phone.trim() || null,
        email: form.email.trim() || null,
      }),
    });
    setForm({ name: '', phone: '', email: '' });
    setOpen(false);
    await load();
  };

  const remove = async (id: string) => {
    if (!confirm('Delete this customer? Customers with appointment history cannot be deleted.')) return;
    await api(`/customers/${id}`, { method: 'DELETE' });
    await load();
  };

  return (
    <>
      <PageHeader
        title="Customers"
        description="Customer profiles collected during the appointment booking flow."
        action={
          <Button onClick={() => setOpen(!open)}>
            {open ? <X size={17} /> : <UserPlus size={17} />} {open ? 'Close' : 'Add customer'}
          </Button>
        }
      />
      {open && (
        <Card className="inline-create">
          <form onSubmit={submit}>
            <div className="form-grid">
              <Field label="Customer name">
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Full name"
                />
              </Field>
              <Field label="Phone number">
                <Input
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  placeholder="e.g. +15551234567"
                />
              </Field>
            </div>
            <div className="form-grid">
              <Field label="Email address">
                <Input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  placeholder="customer@example.com"
                />
              </Field>
            </div>
            <Button>
              <Plus size={17} />
              Save customer
            </Button>
          </form>
        </Card>
      )}
      <Card>
        <div className="table-toolbar">
          <div>
            <h2>Customer directory</h2>
            <p>{items.length} registered customers</p>
          </div>
          <div className="search-box">
            <Search size={17} />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name, phone, or email..."
            />
          </div>
        </div>
        {items.length ? (
          <div className="customer-list">
            {items.map((item) => (
              <div className="customer-row" key={item.id}>
                <span className="avatar large">{item.name?.[0]?.toUpperCase() || '?'}</span>
                <div className="grow">
                  <strong>{item.name || 'Unnamed customer'}</strong>
                  <div className="identity-list">
                    {item.email && (
                      <span>
                        <Badge tone="blue"><Mail size={12} style={{ marginRight: 4 }} />{item.email}</Badge>
                      </span>
                    )}
                    {item.phone && (
                      <span>
                        <Badge tone="neutral"><Phone size={12} style={{ marginRight: 4 }} />{item.phone}</Badge>
                      </span>
                    )}
                    {!item.email && !item.phone && <small>No contact info registered</small>}
                  </div>
                </div>
                <button className="icon-button danger" onClick={() => void remove(item.id)} title="Delete customer">
                  <Trash2 size={17} />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <Empty title="No customers found" text="Customers created during website booking will appear here." />
        )}
      </Card>
    </>
  );
}
