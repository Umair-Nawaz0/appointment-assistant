import { Bot, CalendarDays, ChevronDown, Clock3, ContactRound, ExternalLink, LayoutDashboard, LogOut, Menu, MessageSquareText, Moon, Settings2, Sparkles, Store, Sun, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const links = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/appointments', label: 'Appointments', icon: CalendarDays },
  { to: '/customers', label: 'Customers', icon: ContactRound },
  { to: '/conversations', label: 'Conversations', icon: MessageSquareText },
  { to: '/business', label: 'Business profile', icon: Store },
  { to: '/settings', label: 'Booking settings', icon: Settings2 },
  { to: '/availability', label: 'Availability', icon: Clock3 },
];

export function AppLayout() {
  const { business, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return localStorage.getItem('ai_assistant_theme') === 'dark' ? 'dark' : 'light';
  });

  useEffect(() => {
    localStorage.setItem('ai_assistant_theme', theme);
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const signOut = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="app-shell">
      <button className="mobile-menu" onClick={() => setOpen(!open)} aria-label="Toggle navigation">
        {open ? <X /> : <Menu />}
      </button>
      <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
        <div className="brand">
          <span className="brand-mark">A</span>
          <div>
            <strong>Appointment</strong>
            <small>Assistant</small>
          </div>
        </div>

        <Link to="/chat" target="_blank" rel="noopener noreferrer" className="sidebar-patient-btn" title="Open patient booking and chat page in new tab">
          <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={16} />
            <span>Patient Portal</span>
          </span>
          <ExternalLink size={13} />
        </Link>

        <nav>
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)}>
              <Icon size={19} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <button className="account" onClick={signOut}>
          <span className="avatar">{business?.businessName?.[0]?.toUpperCase()}</span>
          <span>
            <strong>{business?.businessName}</strong>
            <small>{business?.email}</small>
          </span>
          <LogOut size={17} />
        </button>
      </aside>
      <main className="main">
        <div className="topbar">
          <Link to="/chat" target="_blank" rel="noopener noreferrer" className="topbar-patient-link" title="Open live patient chat interface">
            <Bot size={15} />
            <span>Patient Chat View</span>
            <ExternalLink size={12} />
          </Link>
          
          <div className="topbar-actions">
            <div className="admin-theme-switch" role="radiogroup" aria-label="Theme choice">
              <button
                type="button"
                className={`admin-theme-opt ${theme === 'light' ? 'active' : ''}`}
                onClick={() => setTheme('light')}
                title="White Background"
              >
                <Sun size={13} />
                <span>White</span>
              </button>
              <button
                type="button"
                className={`admin-theme-opt ${theme === 'dark' ? 'active' : ''}`}
                onClick={() => setTheme('dark')}
                title="Dark Background"
              >
                <Moon size={13} />
                <span>Dark</span>
              </button>
            </div>

            <div className="topbar-workspace">
              <small>Workspace</small>
              <strong>{business?.businessName}</strong>
            </div>
            <ChevronDown size={17} />
          </div>
        </div>
        <div className="content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
