import {
  AlertCircle,
  Bot,
  Calendar,
  CalendarCheck2,
  CheckCircle2,
  Clock,
  Download,
  Mail,
  MapPin,
  Moon,
  Phone,
  RefreshCw,
  Send,
  Sparkles,
  Sun,
  User,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { useSearchParams } from 'react-router-dom';

type Message = {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  slots?: string[];
  pass?: {
    appointment_id: string;
    customer_name: string;
    customer_phone?: string;
    service_name: string;
    start_datetime: string;
    end_datetime?: string;
    address?: string;
    clinic_name?: string;
  };
};

type ClinicInfo = {
  business: {
    id: string;
    name: string;
    email: string;
    industry: string;
    address: string;
    timezone: string;
  };
};

const THEME_STORAGE_KEY = 'ai_assistant_theme';
const CONV_STORAGE_KEY = 'ai_assistant_conv_id';

export function PatientChatPage() {
  const [searchParams] = useSearchParams();
  const businessIdParam = searchParams.get('business_id');

  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    return saved === 'dark' ? 'dark' : 'light';
  });

  const [clinic, setClinic] = useState<ClinicInfo | null>(null);

  // Customer state & database linkage
  const [customerId, setCustomerId] = useState<string>(
    () => searchParams.get('customer_id') || sessionStorage.getItem('ai_assistant_customer_id') || ''
  );
  const [customerName, setCustomerName] = useState<string>(
    () => searchParams.get('name') || sessionStorage.getItem('ai_assistant_customer_name') || ''
  );
  const [customerPhone, setCustomerPhone] = useState<string>(
    () => searchParams.get('phone') || sessionStorage.getItem('ai_assistant_customer_phone') || ''
  );
  const [customerEmail, setCustomerEmail] = useState<string>(
    () => searchParams.get('email') || sessionStorage.getItem('ai_assistant_customer_email') || ''
  );

  // In-chat customer registration modal state
  const [showRegModal, setShowRegModal] = useState(false);
  const [modalName, setModalName] = useState(customerName);
  const [modalPhone, setModalPhone] = useState(customerPhone);
  const [modalEmail, setModalEmail] = useState(customerEmail);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Sync with searchParams if navigated with parameters
  useEffect(() => {
    const cid = searchParams.get('customer_id');
    const cname = searchParams.get('name');
    const cphone = searchParams.get('phone');
    const cemail = searchParams.get('email');
    if (cid) {
      setCustomerId(cid);
      sessionStorage.setItem('ai_assistant_customer_id', cid);
    }
    if (cname) {
      setCustomerName(cname);
      sessionStorage.setItem('ai_assistant_customer_name', cname);
    }
    if (cphone) {
      setCustomerPhone(cphone);
      sessionStorage.setItem('ai_assistant_customer_phone', cphone);
    }
    if (cemail) {
      setCustomerEmail(cemail);
      sessionStorage.setItem('ai_assistant_customer_email', cemail);
    }
  }, [searchParams]);

  const [conversationId, setConversationId] = useState<string>(() => {
    const saved = sessionStorage.getItem(CONV_STORAGE_KEY);
    if (saved) return saved;
    const newId = crypto.randomUUID();
    sessionStorage.setItem(CONV_STORAGE_KEY, newId);
    return newId;
  });

  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const streamRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync theme
  useEffect(() => {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Load clinic details
  useEffect(() => {
    const url = businessIdParam
      ? `/api/public/clinic-info?business_id=${encodeURIComponent(businessIdParam)}`
      : '/api/public/clinic-info';

    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: ClinicInfo | null) => {
        if (data) {
          setClinic(data);
        }
      })
      .catch((err) => console.warn('Could not fetch clinic info:', err));
  }, [businessIdParam]);

  // Scroll to bottom cleanly inside the chat stream container only (never scrolling window or header)
  useEffect(() => {
    if (streamRef.current) {
      streamRef.current.scrollTo({
        top: streamRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [messages, isThinking]);

  // Extract slots from assistant text if formatted as times (e.g. 09:00 AM, 10:30, 2:00 PM)
  const extractSlotsFromText = (text: string): string[] => {
    const timeMatches = text.match(/\b(?:0?[1-9]|1[0-2]):[0-5][0-9]\s*(?:AM|PM|am|pm)?\b|\b(?:[01]?[0-9]|2[0-3]):[0-5][0-9]\b/g);
    if (!timeMatches || timeMatches.length < 2) return [];
    // Deduplicate
    const unique = Array.from(new Set(timeMatches));
    return unique.slice(0, 6);
  };

  // Helper: check if message indicates a confirmed booking
  const detectBookingPass = (text: string, data?: any) => {
    const lower = text.toLowerCase();
    const isConfirmed =
      lower.includes('confirmed') ||
      lower.includes('booked successfully') ||
      lower.includes('appointment has been scheduled') ||
      data?.action === 'CONFIRMED' ||
      data?.workflow === 'BOOKING_CONFIRMED';

    if (isConfirmed && (data?.appointment_id || lower.includes('appointment'))) {
      return {
        appointment_id: data?.appointment_id || crypto.randomUUID(),
        customer_name: customerName || data?.customer_name || 'Patient',
        customer_phone: customerPhone || data?.customer_phone || '',
        service_name: data?.service_name || 'Doctor Consultation',
        start_datetime: data?.start_datetime || new Date().toISOString(),
        address: clinic?.business?.address || 'Clinic Main Reception',
        clinic_name: clinic?.business?.name || 'CareSync Health',
      };
    }
    return undefined;
  };

  // Helper: Google Calendar URL
  const getGoogleCalendarUrl = (pass: NonNullable<Message['pass']>) => {
    const startIso = new Date(pass.start_datetime).toISOString().replace(/-|:|\.\d+/g, '');
    const endDt = pass.end_datetime
      ? new Date(pass.end_datetime)
      : new Date(new Date(pass.start_datetime).getTime() + 30 * 60000);
    const endIso = endDt.toISOString().replace(/-|:|\.\d+/g, '');
    const title = encodeURIComponent(`${pass.service_name} — ${pass.clinic_name || 'Clinic'}`);
    const details = encodeURIComponent(
      `Appointment at ${pass.clinic_name || 'Clinic'}\nReference: ${pass.appointment_id}\nPatient: ${pass.customer_name}`
    );
    const loc = encodeURIComponent(pass.address || '');
    return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${title}&dates=${startIso}/${endIso}&details=${details}&location=${loc}`;
  };

  // Helper: Download .ICS file
  const downloadIcsFile = (pass: NonNullable<Message['pass']>) => {
    const start = new Date(pass.start_datetime);
    const end = pass.end_datetime ? new Date(pass.end_datetime) : new Date(start.getTime() + 30 * 60000);

    const pad = (n: number) => (n < 10 ? '0' + n : n);
    const formatIcs = (d: Date) =>
      `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}00Z`;

    const content = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//CareSync//AI Assistant//EN',
      'BEGIN:VEVENT',
      `UID:${pass.appointment_id}@caresync`,
      `DTSTAMP:${formatIcs(new Date())}`,
      `DTSTART:${formatIcs(start)}`,
      `DTEND:${formatIcs(end)}`,
      `SUMMARY:${pass.service_name} at ${pass.clinic_name || 'Clinic'}`,
      `DESCRIPTION:Booking Reference: ${pass.appointment_id}\\nPatient: ${pass.customer_name}`,
      `LOCATION:${pass.address || ''}`,
      'STATUS:CONFIRMED',
      'END:VEVENT',
      'END:VCALENDAR',
    ].join('\r\n');

    const blob = new Blob([content], { type: 'text/calendar;charset=utf-8' });
    const link = document.createElement('a');
    link.href = window.URL.createObjectURL(blob);
    link.setAttribute('download', `appointment-${pass.appointment_id.slice(0, 8)}.ics`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Send message handler
  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || isThinking) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsThinking(true);

    try {
      const res = await fetch('/api/public/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          business_id: clinic?.business?.id || businessIdParam || undefined,
          conversation_id: conversationId,
          customer_id: customerId || undefined,
          customer_name: customerName || undefined,
          customer_phone: customerPhone || undefined,
          customer_email: customerEmail || undefined,
          message: text,
        }),
      });

      const resData = await res.json();

      if (resData.data?.customer_id && !customerId) {
        setCustomerId(resData.data.customer_id);
        sessionStorage.setItem('ai_assistant_customer_id', resData.data.customer_id);
      }

      const replyText = resData.reply || 'Your request has been received.';
      const slots = resData.data?.slots || extractSlotsFromText(replyText);
      const pass = detectBookingPass(replyText, resData.data);

      const botMsg: Message = {
        id: crypto.randomUUID(),
        sender: 'assistant',
        text: replyText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        slots: slots.length > 0 ? slots : undefined,
        pass,
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          sender: 'assistant',
          text: 'I am experiencing a momentary connection issue. Please try again or ask for our clinic timings.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          error: true,
        },
      ]);
    } finally {
      setIsThinking(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleRegisterFromChat = async (e: React.FormEvent) => {
    e.preventDefault();
    const activeBizId = clinic?.business?.id || businessIdParam || '';
    if (!activeBizId) return;
    if (!modalName.trim() || !modalPhone.trim()) {
      setModalError('Please enter both your name and phone number.');
      return;
    }

    setModalLoading(true);
    setModalError(null);
    try {
      const res = await fetch('/api/public/customers/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          business_id: activeBizId,
          name: modalName.trim(),
          phone: modalPhone.trim(),
          email: modalEmail.trim() || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Failed to save customer');
      }

      const newCid = data.customer?.id;
      setCustomerId(newCid || '');
      setCustomerName(modalName.trim());
      setCustomerPhone(modalPhone.trim());
      setCustomerEmail(modalEmail.trim());

      if (newCid) sessionStorage.setItem('ai_assistant_customer_id', newCid);
      sessionStorage.setItem('ai_assistant_customer_name', modalName.trim());
      sessionStorage.setItem('ai_assistant_customer_phone', modalPhone.trim());
      if (modalEmail.trim()) {
        sessionStorage.setItem('ai_assistant_customer_email', modalEmail.trim());
      }

      setShowRegModal(false);

      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          sender: 'assistant',
          text: `Thank you, ${modalName.trim()}! Your customer details have been saved in our database. How may I assist you with your booking or inquiries?`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } catch (err: any) {
      setModalError(err.message || 'Error saving customer information');
    } finally {
      setModalLoading(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className={`ai-stage-canvas theme-${theme}`}>
      {/* Background ambient gradient lighting */}
      <div className="ai-stage-glow top" />
      <div className="ai-stage-glow bottom" />

      {/* 1. Executive Top Control Header */}
      <header className="ai-stage-header">
        <div className="ai-stage-brand">
          <div className="ai-stage-live-dot" />
          <span className="ai-stage-title">
            {clinic?.business?.name || 'Appointment Assistant'}
          </span>
        </div>

        <div className="ai-stage-header-actions">
          {/* User Profile / Update Details */}
          <button
            type="button"
            className="ai-stage-user-profile-btn"
            onClick={() => {
              setModalName(customerName);
              setModalPhone(customerPhone);
              setModalEmail(customerEmail);
              setShowRegModal(true);
            }}
            title="Click to view or edit your profile details"
          >
            <div className="ai-stage-user-avatar">
              <User size={14} />
            </div>
            <div className="ai-stage-user-meta">
              <strong className="ai-stage-user-name">
                {customerName || 'Your Profile'}
              </strong>
              {customerPhone && (
                <span className="ai-stage-user-sub">({customerPhone})</span>
              )}
            </div>
            <span className="ai-stage-user-edit-label">
              {customerName ? 'Edit Details' : 'Set Profile'}
            </span>
          </button>

          {/* Theme Switcher (White / Dark) */}
          <div className="ai-stage-theme-switch" role="radiogroup" aria-label="Choose Background Color">
            <button
              type="button"
              className={`ai-stage-theme-opt ${theme === 'light' ? 'active' : ''}`}
              onClick={() => setTheme('light')}
              title="Switch to White Background"
            >
              <Sun size={13} />
              <span>White</span>
            </button>
            <button
              type="button"
              className={`ai-stage-theme-opt ${theme === 'dark' ? 'active' : ''}`}
              onClick={() => setTheme('dark')}
              title="Switch to Dark Background"
            >
              <Moon size={13} />
              <span>Dark</span>
            </button>
          </div>
        </div>
      </header>

      {/* 2. Main Conversational Stream */}
      <main className="ai-stage-body">
        <div className="ai-stage-stream" ref={streamRef}>
          {messages.length === 0 && (
            <div className="ai-stage-starter-hero">
              <div className="ai-stage-starter-icon">
                <Bot size={28} />
              </div>
              <h2 className="ai-stage-starter-title">
                {clinic?.business?.name ? `Welcome to ${clinic.business.name}` : 'Welcome to CareSync Health'}
              </h2>
              <p className="ai-stage-starter-desc">
                How can we help you today? Ask any questions or select a starter prompt below to begin your chat.
              </p>
              <div className="ai-stage-starter-prompts">
                <button
                  type="button"
                  className="ai-stage-starter-prompt-btn"
                  onClick={() => handleSendMessage('I would like to book an appointment')}
                >
                  <Calendar size={14} />
                  <span>Book an appointment</span>
                </button>
                <button
                  type="button"
                  className="ai-stage-starter-prompt-btn"
                  onClick={() => handleSendMessage('What are your available times this week?')}
                >
                  <Clock size={14} />
                  <span>Available times</span>
                </button>
                <button
                  type="button"
                  className="ai-stage-starter-prompt-btn"
                  onClick={() => handleSendMessage('What services and treatments do you offer?')}
                >
                  <Sparkles size={14} />
                  <span>Clinic services</span>
                </button>
              </div>
            </div>
          )}

          {messages.map((m) => {
            const isUser = m.sender === 'user';
            return (
              <div key={m.id} className={`ai-stage-msg-row ${isUser ? 'user' : 'assistant'}`}>
                {!isUser && (
                  <div className="ai-stage-avatar-mini" aria-label="Assistant">
                    <Bot size={15} />
                  </div>
                )}

                <div className="ai-stage-bubble-wrap">
                  <div className={`ai-stage-bubble ${isUser ? 'user' : 'assistant'}`}>
                    <div className="ai-stage-bubble-text">{m.text}</div>

                    {/* Interactive Slot Buttons within message */}
                    {m.slots && m.slots.length > 0 && (
                      <div className="ai-stage-slots-box">
                        <div className="ai-stage-slots-header">
                          <Clock size={13} />
                          <span>Select a time slot:</span>
                        </div>
                        <div className="ai-stage-slots-list">
                          {m.slots.map((s, idx) => (
                            <button
                              key={idx}
                              type="button"
                              className="ai-stage-slot-btn"
                              onClick={() => handleSendMessage(`I would like to choose the ${s} slot`)}
                            >
                              {s}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Verified Digital Clinic Pass Card within message */}
                    {m.pass && (
                      <div className="ai-stage-pass-card">
                        <div className="ai-stage-pass-top">
                          <CheckCircle2 size={20} color="#10b981" />
                          <div>
                            <strong>Appointment Confirmed</strong>
                            <small>Reference: #{m.pass.appointment_id.slice(0, 8).toUpperCase()}</small>
                          </div>
                        </div>

                        <div className="ai-stage-pass-details">
                          <div className="ai-stage-pass-row">
                            <span>Service:</span>
                            <strong>{m.pass.service_name}</strong>
                          </div>
                          <div className="ai-stage-pass-row">
                            <span>Patient:</span>
                            <strong>{m.pass.customer_name}</strong>
                          </div>
                          <div className="ai-stage-pass-row">
                            <span>Date & Time:</span>
                            <strong>
                              {new Date(m.pass.start_datetime).toLocaleDateString(undefined, {
                                weekday: 'short',
                                month: 'short',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                              })}
                            </strong>
                          </div>
                          {m.pass.address && (
                            <div className="ai-stage-pass-row">
                              <span>Location:</span>
                              <strong>{m.pass.address}</strong>
                            </div>
                          )}
                        </div>

                        <div className="ai-stage-pass-actions">
                          <a
                            href={getGoogleCalendarUrl(m.pass)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ai-stage-pass-btn primary"
                          >
                            <CalendarCheck2 size={13} /> Google Calendar
                          </a>
                          <button
                            type="button"
                            className="ai-stage-pass-btn"
                            onClick={() => downloadIcsFile(m.pass!)}
                          >
                            <Download size={13} /> .ICS Pass
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                  <span className="ai-stage-bubble-time">{m.timestamp}</span>
                </div>
              </div>
            );
          })}

          {/* Inline Assistant Typing Indicator */}
          {isThinking && (
            <div className="ai-stage-msg-row assistant">
              <div className="ai-stage-avatar-mini" aria-label="Assistant">
                <Bot size={15} />
              </div>
              <div className="ai-stage-bubble-wrap">
                <div className="ai-stage-bubble assistant thinking">
                  <div className="ai-stage-typing-indicator">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* 3. Sleek Modern Chat Input Dock */}
      <footer className="ai-stage-dock">
        <div className="ai-stage-input-container">
          <input
            ref={inputRef}
            type="text"
            className="ai-stage-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message..."
            disabled={isThinking}
            autoFocus
          />

          <button
            type="button"
            className="ai-stage-send-btn"
            onClick={() => handleSendMessage()}
            disabled={!input.trim() || isThinking}
            aria-label="Send message"
          >
            {isThinking ? (
              <RefreshCw size={17} className="ai-stage-spinner" />
            ) : (
              <Send size={17} />
            )}
          </button>
        </div>
      </footer>

      {/* In-Chat Customer Registration Modal */}
      {showRegModal && (
        <div className="ai-modal-overlay" onClick={() => setShowRegModal(false)}>
          <div className="ai-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="ai-modal-header">
              <div className="ai-modal-title">
                <User size={18} />
                <span>{customerName ? 'Update Your Profile' : 'Your Profile'}</span>
              </div>
              <button
                type="button"
                className="ai-modal-close"
                onClick={() => setShowRegModal(false)}
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>

            <p className="ai-modal-subtitle">
              Keep your contact details up to date for appointment bookings and confirmations.
            </p>

            <form onSubmit={handleRegisterFromChat} className="ai-modal-form">
              <div className="ai-modal-field">
                <label htmlFor="chat-cust-name">Full Name *</label>
                <div className="ai-modal-input-wrap">
                  <User size={15} />
                  <input
                    id="chat-cust-name"
                    type="text"
                    placeholder="e.g. Sardar Umair"
                    value={modalName}
                    onChange={(e) => {
                      setModalName(e.target.value);
                      if (modalError) setModalError(null);
                    }}
                    required
                  />
                </div>
              </div>

              <div className="ai-modal-field">
                <label htmlFor="chat-cust-phone">Phone Number *</label>
                <div className="ai-modal-input-wrap">
                  <Phone size={15} />
                  <input
                    id="chat-cust-phone"
                    type="tel"
                    placeholder="e.g. +92 300 1234567"
                    value={modalPhone}
                    onChange={(e) => {
                      setModalPhone(e.target.value);
                      if (modalError) setModalError(null);
                    }}
                    required
                  />
                </div>
              </div>

              <div className="ai-modal-field">
                <label htmlFor="chat-cust-email">Email Address (Optional)</label>
                <div className="ai-modal-input-wrap">
                  <Mail size={15} />
                  <input
                    id="chat-cust-email"
                    type="email"
                    placeholder="e.g. sardarumairnawazkhan@gmail.com"
                    value={modalEmail}
                    onChange={(e) => setModalEmail(e.target.value)}
                  />
                </div>
              </div>

              {modalError && (
                <div className="ai-modal-alert error">
                  <AlertCircle size={14} />
                  <span>{modalError}</span>
                </div>
              )}

              <div className="ai-modal-actions">
                <button
                  type="submit"
                  className="ai-modal-btn primary"
                  disabled={modalLoading || !modalName.trim() || !modalPhone.trim()}
                >
                  <User size={15} />
                  <span>{modalLoading ? 'Saving...' : customerName ? 'Update Profile' : 'Save Details'}</span>
                </button>
                <button
                  type="button"
                  className="ai-modal-btn secondary"
                  onClick={() => setShowRegModal(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
