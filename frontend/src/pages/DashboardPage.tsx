import { Bot, CalendarCheck2, Clock3, ContactRound, ExternalLink, MessageSquareText, Settings2, TrendingUp, type LucideIcon } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Empty, PageHeader, Spinner, Badge } from '../components/ui';
import { api, formatDate } from '../lib/api';
import type { Appointment } from '../types';

type Summary = {
  metrics: {
    appointmentsToday: number;
    upcomingAppointments: number;
    openConversations: number;
    totalCustomers: number;
  };
  upcoming: Appointment[];
};

export function DashboardPage() {
  const [data, setData] = useState<Summary | null>(null);

  useEffect(() => {
    api<Summary>('/dashboard/summary').then(setData);
  }, []);

  if (!data) return <Spinner />;

  const metrics: { label: string; value: number; Icon: LucideIcon; tone: string }[] = [
    { label: 'Appointments today', value: data.metrics.appointmentsToday, Icon: CalendarCheck2, tone: 'violet' },
    { label: 'Next 7 days', value: data.metrics.upcomingAppointments, Icon: TrendingUp, tone: 'blue' },
    { label: 'Open conversations', value: data.metrics.openConversations, Icon: MessageSquareText, tone: 'amber' },
    { label: 'Total customers', value: data.metrics.totalCustomers, Icon: ContactRound, tone: 'green' },
  ];

  return (
    <>
      <PageHeader
        title="Good to see you"
        description="Here’s what is happening across your AI assistant today."
        action={
          <div style={{ display: 'flex', gap: '10px' }}>
            <Link className="button button-secondary" to="/chat" target="_blank" rel="noopener noreferrer">
              <ExternalLink size={15} /> Patient Chat View
            </Link>
            <Link className="button" to="/appointments">
              New appointment
            </Link>
          </div>
        }
      />
      <div className="metrics">
        {metrics.map(({ label, value, Icon, tone }) => (
          <Card key={label} className={`metric metric-${tone}`}>
            <span className="metric-icon"><Icon size={21} /></span>
            <div>
              <strong>{value}</strong>
              <span>{label}</span>
            </div>
          </Card>
        ))}
      </div>
      <div className="dashboard-grid">
        <Card>
          <div className="section-head">
            <div>
              <h2>Upcoming appointments</h2>
              <p>Your next confirmed and pending bookings.</p>
            </div>
            <Link to="/appointments">View all</Link>
          </div>
          {data.upcoming.length ? (
            <div className="list">
              {data.upcoming.map((item) => (
                <div className="list-row" key={item.id}>
                  <span className="date-tile">
                    <strong>{new Date(item.scheduledStart).getDate()}</strong>
                    <small>{new Date(item.scheduledStart).toLocaleString(undefined, { month: 'short' })}</small>
                  </span>
                  <div className="grow">
                    <strong>{item.customerName || 'Unnamed customer'}</strong>
                    <small>{formatDate(item.scheduledStart)}</small>
                  </div>
                  <Badge tone={item.status === 'CONFIRMED' ? 'green' : 'amber'}>{item.status}</Badge>
                </div>
              ))}
            </div>
          ) : (
            <Empty title="No upcoming appointments" text="New bookings will appear here." />
          )}
        </Card>
        <Card className="setup-card">
          <div className="section-head">
            <div>
              <h2>Assistant configuration</h2>
              <p>Essentials for your website booking assistant.</p>
            </div>
            <Settings2 size={22} />
          </div>
          <div className="readiness">
            <div>
              <span>Website AI Assistant</span>
              <strong>Active & Ready</strong>
            </div>
            <p className="readiness-help">Visitors can chat naturally, check live availability, and schedule appointments directly on your website.</p>
            <Link className="button" to="/chat" target="_blank" rel="noopener noreferrer">
              <Bot size={16} /> Open Patient Chat Portal
            </Link>
            <Link className="button button-secondary" to="/availability">
              <Clock3 size={16} /> Manage opening hours
            </Link>
            <Link className="text-link" to="/settings">
              Manage booking policies
            </Link>
          </div>
        </Card>
      </div>
    </>
  );
}
