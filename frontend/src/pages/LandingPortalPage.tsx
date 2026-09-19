import {
  AlertCircle,
  ArrowRight,
  Bot,
  Building2,
  CalendarCheck2,
  CheckCircle2,
  Clock,
  ExternalLink,
  Lock,
  Mail,
  MapPin,
  MessageSquareText,
  Moon,
  Phone,
  ShieldCheck,
  Sparkles,
  Sun,
  User,
  UserCheck,
  UserPlus,
  Users,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import agentImg from '../assets/agent_hd.png';

const THEME_STORAGE_KEY = 'ai_assistant_theme';

type PublicBusiness = {
  id: string;
  name: string;
  email: string;
  industry: string;
  address: string;
  city: string;
  timezone: string;
};

export function LandingPortalPage() {
  const { business, loading } = useAuth();
  const navigate = useNavigate();

  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    return saved === 'dark' ? 'dark' : 'light';
  });

  const [businesses, setBusinesses] = useState<PublicBusiness[]>([]);
  const [selectedBusinessId, setSelectedBusinessId] = useState<string>('');
  const [loadingBusinesses, setLoadingBusinesses] = useState(true);

  // Customer state for database registration
  const [customerName, setCustomerName] = useState(() => sessionStorage.getItem('ai_assistant_customer_name') || '');
  const [customerPhone, setCustomerPhone] = useState(() => sessionStorage.getItem('ai_assistant_customer_phone') || '');
  const [customerEmail, setCustomerEmail] = useState(() => sessionStorage.getItem('ai_assistant_customer_email') || '');
  const [isRegistering, setIsRegistering] = useState(false);
  const [registerError, setRegisterError] = useState<string | null>(null);
  const [registerSuccess, setRegisterSuccess] = useState<string | null>(null);

  useEffect(() => {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    fetch('/api/public/businesses')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.businesses && Array.isArray(data.businesses)) {
          setBusinesses(data.businesses);
          if (data.businesses.length > 0) {
            setSelectedBusinessId(data.businesses[0].id);
          }
        }
      })
      .catch((err) => console.warn('Could not load businesses:', err))
      .finally(() => setLoadingBusinesses(false));
  }, []);

  const selectedBusiness = businesses.find((b) => b.id === selectedBusinessId) || businesses[0];

  const handleRegisterAndChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBusinessId) return;
    if (!customerName.trim() || !customerPhone.trim()) {
      setRegisterError('Please provide your name and phone number.');
      return;
    }

    setIsRegistering(true);
    setRegisterError(null);
    try {
      const res = await fetch('/api/public/customers/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          business_id: selectedBusinessId,
          name: customerName.trim(),
          phone: customerPhone.trim(),
          email: customerEmail.trim() || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Failed to save customer');
      }

      const custId = data.customer?.id;
      if (custId) sessionStorage.setItem('ai_assistant_customer_id', custId);
      sessionStorage.setItem('ai_assistant_customer_name', customerName.trim());
      sessionStorage.setItem('ai_assistant_customer_phone', customerPhone.trim());
      if (customerEmail.trim()) {
        sessionStorage.setItem('ai_assistant_customer_email', customerEmail.trim());
      }

      setRegisterSuccess(
        `Registered as customer of ${selectedBusiness?.name || 'clinic'} in database! Starting chat...`
      );

      setTimeout(() => {
        const p = new URLSearchParams();
        p.set('business_id', selectedBusinessId);
        if (custId) p.set('customer_id', custId);
        p.set('name', customerName.trim());
        p.set('phone', customerPhone.trim());
        if (customerEmail.trim()) p.set('email', customerEmail.trim());
        navigate(`/chat?${p.toString()}`);
      }, 600);
    } catch (err: any) {
      setRegisterError(err.message || 'Could not register customer');
      setIsRegistering(false);
    }
  };

  const handleStartGuestChat = () => {
    const p = new URLSearchParams();
    if (selectedBusinessId) p.set('business_id', selectedBusinessId);
    navigate(`/chat?${p.toString()}`);
  };

  return (
    <div className={`portal-root theme-${theme}`}>
      {/* Background Ambient Glows */}
      <div className="portal-ambient-glow glow-1" />
      <div className="portal-ambient-glow glow-2" />

      {/* Navigation Topbar */}
      <header className="portal-header">
        <div className="portal-brand">
          <span className="portal-brand-icon">
            <CalendarCheck2 size={22} color="#ffffff" />
          </span>
          <div className="portal-brand-text">
            <strong>Appointment Assistant</strong>
            <span className="portal-brand-sub">AI Automation & Management Portal</span>
          </div>
        </div>

        <div className="portal-header-right">
          {/* Theme switcher (Dark / White) */}
          <div className="portal-theme-switch" role="radiogroup" aria-label="Theme toggle">
            <button
              type="button"
              className={`portal-theme-btn ${theme === 'light' ? 'active' : ''}`}
              onClick={() => setTheme('light')}
              title="Switch to White Background"
            >
              <Sun size={13} />
              <span>White</span>
            </button>
            <button
              type="button"
              className={`portal-theme-btn ${theme === 'dark' ? 'active' : ''}`}
              onClick={() => setTheme('dark')}
              title="Switch to Dark Background"
            >
              <Moon size={13} />
              <span>Dark</span>
            </button>
          </div>

          <div className="portal-live-status">
            <span className="portal-pulse-dot" />
            <span className="portal-status-label">n8n Live Workflow</span>
          </div>
        </div>
      </header>

      {/* Main Hero Container */}
      <main className="portal-container">
        <div className="portal-hero">
          <div className="portal-badge-pill">
            <Sparkles size={14} />
            <span>Select Your Destination</span>
          </div>
          <h1 className="portal-title">Welcome to Appointment Assistant</h1>
          <p className="portal-subtitle">
            Sign in to manage your clinic and appointments, or open the instant 24/7 AI chat assistant with no login required.
          </p>
        </div>

        {/* Dual Portal Selection Cards */}
        <div className="portal-cards-grid">
          {/* Option 1: Company / Clinic Portal */}
          <div className="portal-card company-card">
            <div className="portal-card-badge company-badge">
              <Building2 size={13} />
              <span>Company & Staff Portal</span>
            </div>

            <div className="portal-card-header">
              <div className="portal-card-icon company-icon-wrap">
                <ShieldCheck size={28} />
              </div>
              <div>
                <h2>Company Workspace & Admin</h2>
                <p>For clinic owners, managers, and doctors</p>
              </div>
            </div>

            <p className="portal-card-desc">
              Sign up or log in to access the full administrative dashboard. Manage bookings, view live patient conversation histories, configure operating hours, and customize services.
            </p>

            <ul className="portal-features-list">
              <li>
                <CheckCircle2 size={16} className="feature-check company" />
                <span>Full appointment calendar and booking management</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="feature-check company" />
                <span>Real-time conversation logs & patient records</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="feature-check company" />
                <span>Custom business hours, slot duration, and closures</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="feature-check company" />
                <span>Performance analytics & customer directory</span>
              </li>
            </ul>

            <div className="portal-card-actions">
              {business ? (
                <div className="portal-logged-in-box">
                  <div className="portal-user-tag">
                    <UserCheck size={16} />
                    <span>Signed in as <strong>{business.businessName}</strong></span>
                  </div>
                  <button
                    type="button"
                    className="portal-btn portal-btn-primary"
                    onClick={() => navigate('/dashboard')}
                  >
                    Go to Admin Dashboard <ArrowRight size={16} />
                  </button>
                </div>
              ) : (
                <div className="portal-btn-row">
                  <Link to="/login" className="portal-btn portal-btn-primary">
                    Company Sign In <ArrowRight size={16} />
                  </Link>
                  <Link to="/signup" className="portal-btn portal-btn-secondary">
                    Create Company Account
                  </Link>
                </div>
              )}
            </div>
          </div>

          {/* Option 2: Patient & User Chat (Public - No Login) */}
          <div className="portal-card chat-card">
            <div className="portal-card-badge chat-badge">
              <Bot size={13} />
              <span>Public Access • No Login Required</span>
            </div>

            <div className="portal-card-header">
              <div className="portal-card-icon chat-icon-wrap">
                <img src={agentImg} alt="AI Assistant" className="portal-agent-avatar" />
              </div>
              <div>
                <h2>Patient & User Chat Assistant</h2>
                <p>Instant 24/7 AI Receptionist</p>
              </div>
            </div>

            <p className="portal-card-desc">
              Open to anyone without authentication. Chat directly with the AI receptionist to check doctor availability, ask questions about the clinic, and book an appointment with instant confirmation.
            </p>

            <ul className="portal-features-list">
              <li>
                <CheckCircle2 size={16} className="feature-check chat" />
                <span><strong>No authentication needed</strong> — ask questions anytime</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="feature-check chat" />
                <span>Directly powered by the intelligent <strong>n8n workflow</strong></span>
              </li>
              <li>
                <CheckCircle2 size={16} className="feature-check chat" />
                <span>Check live available times & book appointments</span>
              </li>
              <li>
                <CheckCircle2 size={16} className="feature-check chat" />
                <span>Automatic email confirmation & calendar invite (.ics)</span>
              </li>
            </ul>

            {/* Business / Company Selector */}
            <div className="portal-business-box">
              <div className="portal-business-box-label">
                <Building2 size={15} />
                <span>Select Business / Company</span>
              </div>
              <p className="portal-business-box-help">
                Choose which clinic or company you want to book with or become a customer of:
              </p>

              {loadingBusinesses ? (
                <div className="portal-business-loading">Loading registered businesses...</div>
              ) : businesses.length === 0 ? (
                <div className="portal-business-loading">No active businesses available</div>
              ) : (
                <div className="portal-business-select-wrap">
                  <select
                    className="portal-business-select"
                    value={selectedBusinessId}
                    onChange={(e) => setSelectedBusinessId(e.target.value)}
                    aria-label="Select business or company"
                  >
                    {businesses.map((biz) => (
                      <option key={biz.id} value={biz.id}>
                        {biz.name} — {biz.industry || 'Healthcare'}{biz.city ? ` (${biz.city})` : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {selectedBusiness && (
                <div className="portal-selected-business-card">
                  <div className="portal-selected-top">
                    <span className="portal-selected-name">{selectedBusiness.name}</span>
                    <span className="portal-selected-badge">{selectedBusiness.industry || 'Healthcare'}</span>
                  </div>
                  <div className="portal-selected-meta">
                    <span className="portal-selected-city">
                      <MapPin size={12} />
                      {selectedBusiness.city || selectedBusiness.address || 'Online Clinic'}
                    </span>
                    <span className="portal-selected-status">
                      <span className="portal-pulse-dot" /> AI Assistant Online
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Customer Registration & Database Linkage */}
            <div className="portal-customer-reg-box">
              <div className="portal-customer-reg-header">
                <div className="portal-customer-reg-title">
                  <UserCheck size={16} />
                  <span>Register as Customer</span>
                </div>
                <span className="portal-customer-badge">PostgreSQL Database</span>
              </div>
              <p className="portal-customer-reg-desc">
                Register your details with <strong>{selectedBusiness ? selectedBusiness.name : 'the selected clinic'}</strong> to store your customer record in the database, view your past history, and book consultations:
              </p>

              <form onSubmit={handleRegisterAndChat} className="portal-customer-form">
                <div className="portal-cust-inputs-grid">
                  <div className="portal-cust-field">
                    <label htmlFor="cust-name-input">Full Name *</label>
                    <div className="portal-cust-input-field">
                      <User size={15} />
                      <input
                        id="cust-name-input"
                        type="text"
                        placeholder="e.g. Sardar Umair"
                        value={customerName}
                        onChange={(e) => {
                          setCustomerName(e.target.value);
                          if (registerError) setRegisterError(null);
                        }}
                        required
                      />
                    </div>
                  </div>

                  <div className="portal-cust-field">
                    <label htmlFor="cust-phone-input">Phone Number *</label>
                    <div className="portal-cust-input-field">
                      <Phone size={15} />
                      <input
                        id="cust-phone-input"
                        type="tel"
                        placeholder="e.g. +92 300 1234567"
                        value={customerPhone}
                        onChange={(e) => {
                          setCustomerPhone(e.target.value);
                          if (registerError) setRegisterError(null);
                        }}
                        required
                      />
                    </div>
                  </div>

                  <div className="portal-cust-field full-width">
                    <label htmlFor="cust-email-input">Email Address (Optional for confirmations)</label>
                    <div className="portal-cust-input-field">
                      <Mail size={15} />
                      <input
                        id="cust-email-input"
                        type="email"
                        placeholder="e.g. sardarumairnawazkhan@gmail.com"
                        value={customerEmail}
                        onChange={(e) => setCustomerEmail(e.target.value)}
                      />
                    </div>
                  </div>
                </div>

                {registerError && (
                  <div className="portal-cust-alert error">
                    <AlertCircle size={14} />
                    <span>{registerError}</span>
                  </div>
                )}
                {registerSuccess && (
                  <div className="portal-cust-alert success">
                    <CheckCircle2 size={14} />
                    <span>{registerSuccess}</span>
                  </div>
                )}

                <div className="portal-cust-actions-row">
                  <button
                    type="submit"
                    className="portal-btn portal-btn-register-chat"
                    disabled={isRegistering || !selectedBusinessId}
                  >
                    <Sparkles size={16} />
                    <span>
                      {isRegistering
                        ? 'Saving Customer in Database...'
                        : selectedBusiness
                        ? `Register as Customer & Chat with ${selectedBusiness.name}`
                        : 'Register Customer & Start Chat'}
                    </span>
                    <ArrowRight size={16} />
                  </button>

                  <button
                    type="button"
                    className="portal-btn portal-btn-guest"
                    onClick={handleStartGuestChat}
                    title="Start chat as a guest without pre-registering"
                  >
                    <span>Chat as Guest</span>
                  </button>
                </div>
              </form>
            </div>

            <div className="portal-card-actions">
              <div className="portal-card-footnote">
                <Clock size={13} />
                <span>Available 24/7 • Real-time database sync • Powered by AI</span>
              </div>
            </div>
          </div>
        </div>

        {/* Architecture & Verification Footer */}
        <div className="portal-system-banner">
          <div className="portal-sys-item">
            <span className="portal-dot green" />
            <div>
              <strong>n8n Automation Workflow</strong>
              <small>Handles booking, validation, and Gmail notifications</small>
            </div>
          </div>
          <div className="portal-sys-divider" />
          <div className="portal-sys-item">
            <span className="portal-dot green" />
            <div>
              <strong>FastAPI + PostgreSQL Backend</strong>
              <small>Secure appointment scheduling & data storage</small>
            </div>
          </div>
          <div className="portal-sys-divider" />
          <div className="portal-sys-item">
            <span className="portal-dot green" />
            <div>
              <strong>Public & Private Dual Access</strong>
              <small>Open public chat for patients • Secure admin portal for clinics</small>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
