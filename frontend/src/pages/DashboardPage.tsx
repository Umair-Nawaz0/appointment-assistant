import { CalendarCheck2, Clock3, ContactRound, MessageSquareText, Settings2, TrendingUp, type LucideIcon } from 'lucide-react';
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
        title="Operations Overview"
        description="Monitor real-time appointments, patient conversations, and booking schedules."
        action={
          <div style={{ display: 'flex', gap: '10px' }}>
            <Link className="button button-secondary" to="/conversations">
              <MessageSquareText size={15} /> All Conversations
            </Link>
            <Link className="button" to="/appointments">
              <CalendarCheck2 size={15} /> Book Appointment
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
              <p>Next scheduled patient appointments and consultations.</p>
            </div>
            <Link to="/appointments">View all &rarr;</Link>
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
              <h2>System Status</h2>
              <p>Operational health & quick controls</p>
            </div>
            <Settings2 size={22} />
          </div>
          <div className="readiness">
            <div>
              <span>AI Booking Agent</span>
              <span className="badge badge-green">Operational</span>
            </div>
            <p className="readiness-help">The AI assistant is active, qualifying patients and booking appointments according to your operating hours.</p>
            <Link className="button" to="/conversations">
              <MessageSquareText size={16} /> View Live Conversations
            </Link>
            <Link className="button button-secondary" to="/availability">
              <Clock3 size={16} /> Manage Schedule
            </Link>
            <Link className="text-link" to="/settings">
              Edit Booking Rules &rarr;
            </Link>
          </div>
        </Card>
      </div>
    </>
  );
}
