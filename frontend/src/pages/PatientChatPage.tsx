import {
  Building2,
  Calendar,
  CalendarCheck2,
  CheckCircle2,
  Clock,
  Download,
  ExternalLink,
  Home,
  MapPin,
  Moon,
  RefreshCw,
  RotateCcw,
  Send,
  Sparkles,
  Sun,
  User,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import agentImg from '../assets/agent_hd.png';

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

const QUICK_ACTIONS = [
  { label: 'Book an appointment', prompt: 'I want to book an appointment' },
  { label: 'Available times today', prompt: 'What appointment times are open today?' },
  { label: 'Available times tomorrow', prompt: 'What times are available tomorrow?' },
  { label: 'Clinic hours & location', prompt: 'What are your clinic hours and address?' },
  { label: 'Reschedule / Cancel', prompt: 'I need to reschedule or cancel my appointment' },
];

export function PatientChatPage() {
  const [searchParams] = useSearchParams();
  const businessIdParam = searchParams.get('business_id');

  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    return saved === 'dark' ? 'dark' : 'light';
  });

  const [clinic, setClinic] = useState<ClinicInfo | null>(null);
  const [conversationId, setConversationId] = useState<string>(() => {
    const saved = sessionStorage.getItem(CONV_STORAGE_KEY);
    if (saved) return saved;
    const newId = crypto.randomUUID();
    sessionStorage.setItem(CONV_STORAGE_KEY, newId);
    return newId;
  });

  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [thinkingStatus, setThinkingStatus] = useState('Thinking...');

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome-1',
      sender: 'assistant',
      text: 'Hello! I am your AI Appointment Assistant. How can I help you today? You can ask me to book a consultation, check doctor availability, or find our clinic timings.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

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
          setMessages((prev) => {
            if (prev.length === 1 && prev[0].id === 'welcome-1') {
              return [
                {
                  id: 'welcome-1',
                  sender: 'assistant',
                  text: `Hello! I am your AI Appointment Assistant for ${data.business.name}. How can I assist you with your booking today?`,
                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                },
              ];
            }
            return prev;
          });
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
        customer_name: data?.customer_name || 'Patient',
        customer_phone: data?.customer_phone || '',
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
    setThinkingStatus('Processing your request...');

    // Dynamic thinking statuses for high-tech feeling
    const statusTimer = setTimeout(() => {
      setThinkingStatus('Checking schedule availability...');
    }, 900);

    try {
      const res = await fetch('/api/public/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          business_id: clinic?.business?.id || businessIdParam || undefined,
          conversation_id: conversationId,
          message: text,
        }),
      });

      const resData = await res.json();
      clearTimeout(statusTimer);

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
      clearTimeout(statusTimer);
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

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleResetChat = () => {
    const newId = crypto.randomUUID();
    setConversationId(newId);
    sessionStorage.setItem(CONV_STORAGE_KEY, newId);
    setMessages([
      {
        id: crypto.randomUUID(),
        sender: 'assistant',
        text: `Conversation restarted. How can I help you today?`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  };

  return (
    <div className={`ai-stage-canvas theme-${theme}`}>
      {/* Background ambient gradient lighting */}
      <div className="ai-stage-glow top" />
      <div className="ai-stage-glow bottom" />

      {/* 1. Minimal Top Control Header (Only Assistant Status & Controls) */}
      <header className="ai-stage-header">
        <div className="ai-stage-brand">
          <div className="ai-stage-live-dot" />
          <span className="ai-stage-title">
            {clinic?.business?.name ? `${clinic.business.name} Assistant` : 'CareSync AI Assistant'}
          </span>
          <span className="ai-stage-badge">Public • No Login Required</span>
        </div>

        <div className="ai-stage-header-actions">
          {/* Link back to Portal Home */}
          <Link to="/" className="ai-stage-nav-pill" title="Return to Portal Selection">
            <Home size={13} />
            <span>Portal Home</span>
          </Link>

          {/* Link to Company / Staff Portal */}
          <Link to="/login" className="ai-stage-nav-pill company-pill" title="Company & Staff Sign In">
            <Building2 size={13} />
            <span>Company Portal</span>
          </Link>

          {/* Background Choice Switch (White / Dark) */}
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

          <button
            type="button"
            className="ai-stage-icon-btn"
            onClick={handleResetChat}
            title="Start New Chat"
            aria-label="New chat"
          >
            <RotateCcw size={15} />
          </button>
        </div>
      </header>

      {/* 2. Main Conversational Stream */}
      <main className="ai-stage-body">
        <div className="ai-stage-stream" ref={streamRef}>
          {messages.map((m) => {
            const isUser = m.sender === 'user';
            return (
              <div key={m.id} className={`ai-stage-msg-row ${isUser ? 'user' : 'assistant'}`}>
                {!isUser && (
                  <div className="ai-stage-avatar-mini">
                    <img src={agentImg} alt="AI Assistant" />
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

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* 3. Central Living AI Agent & Command Dock */}
      <footer className="ai-stage-dock">
        {/* The 3D Living AI Agent Character above the chatbar */}
        <div className={`ai-stage-agent-box ${isThinking ? 'thinking' : 'idle'}`}>
          <div className="ai-stage-agent-stage">
            {/* 3D Gyroscopic Rings */}
            <div className="ai-stage-gyro-ring ring-one" />
            <div className="ai-stage-gyro-ring ring-two" />
            <div className="ai-stage-agent-aura" />
            <div className="ai-stage-agent-shadow" />

            {/* Living Agent Avatar */}
            <img
              src={agentImg}
              alt="AI Assistant"
              className={`ai-stage-agent-character ${isThinking ? 'pulsing' : ''}`}
            />
          </div>

          {/* Cognitive HUD / Live status display */}
          <div className="ai-stage-cognitive-hud">
            {isThinking ? (
              <div className="ai-stage-thinking-state">
                <div className="ai-stage-wave-bars">
                  <span className="wave-bar" />
                  <span className="wave-bar" />
                  <span className="wave-bar" />
                  <span className="wave-bar" />
                </div>
                <span className="ai-stage-thinking-label">{thinkingStatus}</span>
              </div>
            ) : (
              <div className="ai-stage-idle-state">
                <span className="ai-stage-idle-indicator" />
                <span className="ai-stage-idle-label">AI Assistant Ready</span>
              </div>
            )}
          </div>
        </div>

        {/* Quick Suggestion Action Chips */}
        <div className="ai-stage-chips-row">
          {QUICK_ACTIONS.map((action, i) => (
            <button
              key={i}
              type="button"
              className="ai-stage-chip"
              onClick={() => handleSendMessage(action.prompt)}
              disabled={isThinking}
            >
              <Sparkles size={12} color="#0284c7" />
              <span>{action.label}</span>
            </button>
          ))}
        </div>

        {/* Modern Large Chat Input Bar */}
        <div className="ai-stage-input-container">
          <input
            ref={inputRef}
            type="text"
            className="ai-stage-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message to book or ask a question..."
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
    </div>
  );
}
