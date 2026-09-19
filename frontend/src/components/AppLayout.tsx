import {
  CalendarDays,
  Clock3,
  ContactRound,
  Home,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquareText,
  Moon,
  Settings2,
  Store,
  Sun,
  X
} from 'lucide-react';
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
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

  const signOut = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className={`app-shell theme-${theme}`}>
      <button className="mobile-menu" onClick={() => setOpen(!open)} aria-label="Toggle navigation">
        {open ? <X /> : <Menu />}
      </button>
      <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
        <div className="brand">
          <span className="brand-mark">A</span>
          <div>
            <strong>Appointment</strong>
            <small>Admin Console</small>
          </div>
        </div>

        <nav>
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)}>
              <Icon size={19} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <button className="account" onClick={signOut} title="Click to Sign Out">
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
          <div className="topbar-left-actions">
            <Link to="/" className="topbar-portal-link" title="Return to Portal Selection">
              <Home size={14} />
              <span>Main Portal</span>
            </Link>
            <div className="topbar-badge-online">
              <span className="status-dot" />
              <span>System Online</span>
            </div>
          </div>
          
          <div className="topbar-actions">
            <div className="admin-theme-switch" role="radiogroup" aria-label="Theme choice">
              <button
                type="button"
                className={`admin-theme-opt ${theme === 'light' ? 'active' : ''}`}
                onClick={() => setTheme('light')}
                title="Light Background"
              >
                <Sun size={13} />
                <span>Light</span>
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
            <button className="topbar-logout-btn" onClick={signOut} title="Sign out">
              <LogOut size={16} />
            </button>
          </div>
        </div>
        <div className="content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
