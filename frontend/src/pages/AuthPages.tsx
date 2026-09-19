import { ArrowRight, CalendarCheck2, CheckCircle2, Eye, EyeOff, KeyRound, MailCheck } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';
import { Button, Field, Input, Notice } from '../components/ui';

function AuthShell({eyebrow,title,subtitle,children}:{eyebrow:string;title:string;subtitle:string;children:React.ReactNode}){
  return <div className="auth-shell"><section className="auth-panel">
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
      <Link className="auth-brand" to="/"><span className="brand-mark">A</span><strong>Appointment Assistant</strong></Link>
      <Link to="/chat" style={{ fontSize: '0.8rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}>
        <span>Patient Chat</span> &rarr;
      </Link>
    </div>
    <div className="auth-copy"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{subtitle}</p>{children}</div>
    <div style={{ marginTop: 'auto', paddingTop: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--line)' }}>
      <small className="auth-footer">Secure company workspace</small>
      <Link to="/" style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>&larr; Back to Portal</Link>
    </div>
  </section><aside className="auth-art"><div className="art-orb art-one"/><div className="art-orb art-two"/><div className="quote-card"><CalendarCheck2 size={28}/><h2>One calm place for every appointment.</h2><p>Manage conversations, customers, availability, and bookings without losing the human touch.</p><div className="mini-stats"><span><strong>6</strong>channels</span><span><strong>24/7</strong>ready</span><span><strong>1</strong>inbox</span></div></div></aside></div>;
}

function PasswordInput({value,onChange,autoComplete='current-password'}:{value:string;onChange:(v:string)=>void;autoComplete?:string}){
  const [visible,setVisible]=useState(false);return <div className="password-wrap"><Input type={visible?'text':'password'} value={value} onChange={e=>onChange(e.target.value)} autoComplete={autoComplete} required/><button type="button" onClick={()=>setVisible(!visible)} aria-label="Toggle password">{visible?<EyeOff size={18}/>:<Eye size={18}/>}</button></div>;
}

export function LoginPage(){
  const {business,login}=useAuth();const navigate=useNavigate();const [email,setEmail]=useState('');const [password,setPassword]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  if(business)return <Navigate to="/dashboard" replace/>;
  const submit=async(e:FormEvent)=>{e.preventDefault();setError('');setBusy(true);try{await login(email,password);navigate('/dashboard');}catch(err){setError(err instanceof Error?err.message:'Unable to sign in.');}finally{setBusy(false)}};
  return <AuthShell eyebrow="Welcome back" title="Sign in to your workspace" subtitle="Your customers and schedule are waiting."><form className="auth-form" onSubmit={submit}>{error&&<Notice kind="error">{error}</Notice>}<Field label="Business email"><Input type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email" required/></Field><Field label="Password"><PasswordInput value={password} onChange={setPassword}/></Field><div className="form-row between"><label className="check"><input type="checkbox"/>Remember me</label><Link to="/forgot-password">Forgot password?</Link></div><Button disabled={busy}>{busy?'Signing in…':<>Sign in <ArrowRight size={17}/></>}</Button><p className="form-switch">New here? <Link to="/signup">Create your workspace</Link></p></form></AuthShell>;
}

export function SignupPage(){
  const navigate=useNavigate();const [form,setForm]=useState({businessName:'',email:'',password:'',industry:'',timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC'});const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  const change=(key:string,value:string)=>setForm(prev=>({...prev,[key]:value}));
  const submit=async(e:FormEvent)=>{e.preventDefault();setError('');setBusy(true);try{const result=await api<{message:string;email:string;devCode?:string}>('/auth/signup',{method:'POST',body:JSON.stringify({...form,industry:form.industry||undefined})});navigate('/verify-email',{state:result});}catch(err){setError(err instanceof Error?err.message:'Unable to create workspace.');}finally{setBusy(false)}};
  return <AuthShell eyebrow="Get started" title="Create your business workspace" subtitle="A focused dashboard for your AI receptionist."><form className="auth-form" onSubmit={submit}>{error&&<Notice kind="error">{error}</Notice>}<Field label="Business name"><Input value={form.businessName} onChange={e=>change('businessName',e.target.value)} required/></Field><Field label="Business email"><Input type="email" value={form.email} onChange={e=>change('email',e.target.value)} autoComplete="email" required/></Field><Field label="Password" hint="At least 10 characters with upper, lower, and a number."><PasswordInput value={form.password} onChange={v=>change('password',v)} autoComplete="new-password"/></Field><div className="form-grid"><Field label="Industry (optional)"><Input value={form.industry} onChange={e=>change('industry',e.target.value)} placeholder="Healthcare, salon…"/></Field><Field label="Timezone"><Input value={form.timezone} onChange={e=>change('timezone',e.target.value)} required/></Field></div><Button disabled={busy}>{busy?'Creating…':<>Create workspace <ArrowRight size={17}/></>}</Button><p className="form-switch">Already have an account? <Link to="/login">Sign in</Link></p></form></AuthShell>;
}

export function VerifyEmailPage(){
  const location=useLocation();const initial=(location.state??{}) as {email?:string;devCode?:string};const [email,setEmail]=useState(initial.email??'');const [code,setCode]=useState(initial.devCode??'');const [status,setStatus]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  const submit=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError('');try{const result=await api<{message:string}>('/auth/verify-email',{method:'POST',body:JSON.stringify({email,code})});setStatus(result.message);}catch(err){setError(err instanceof Error?err.message:'Verification failed.');}finally{setBusy(false)}};
  const resend=async()=>{setBusy(true);setError('');try{const result=await api<{message:string;devCode?:string}>('/auth/resend-verification',{method:'POST',body:JSON.stringify({email})});setStatus(result.message);if(result.devCode)setCode(result.devCode);}catch(err){setError(err instanceof Error?err.message:'Unable to resend code.');}finally{setBusy(false)}};
  return <AuthShell eyebrow="One last step" title={status?'Email verified':'Verify your business email'} subtitle="Enter the six-digit code sent to your email.">{status&&status.startsWith('Email verified')?<div className="auth-result"><MailCheck size={42}/><Notice>{status}</Notice><Link className="button" to="/login">Continue to sign in</Link></div>:<form className="auth-form" onSubmit={submit}>{error&&<Notice kind="error">{error}</Notice>}{status&&<Notice>{status}</Notice>}<Field label="Business email"><Input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></Field><Field label="Verification code"><Input value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,'').slice(0,6))} inputMode="numeric" pattern="[0-9]{6}" autoComplete="one-time-code" required/></Field><Button disabled={busy||code.length!==6}>{busy?'Checking…':'Verify email'}</Button><button className="dev-link" type="button" disabled={busy||!email} onClick={()=>void resend()}>Send a new code</button></form>}</AuthShell>;
}

export function ForgotPasswordPage(){
  const navigate=useNavigate();const [email,setEmail]=useState('');const [result,setResult]=useState<{message:string;devCode?:string}|null>(null);const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  const submit=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError('');try{setResult(await api('/auth/forgot-password',{method:'POST',body:JSON.stringify({email})}));}catch(err){setError(err instanceof Error?err.message:'Request failed.');}finally{setBusy(false)}};
  return <AuthShell eyebrow="Account recovery" title="Reset your password" subtitle="Enter your email and we’ll send a six-digit reset code."><form className="auth-form" onSubmit={submit}>{error&&<Notice kind="error">{error}</Notice>}{result&&<Notice>{result.message}</Notice>}<Field label="Business email"><Input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></Field><Button disabled={busy}>{busy?'Sending…':<>Send reset code <ArrowRight size={17}/></>}</Button>{result&&<button className="dev-link" type="button" onClick={()=>navigate('/reset-password',{state:{email,devCode:result.devCode}})}>Enter reset code</button>}<p className="form-switch"><Link to="/login">Back to sign in</Link></p></form></AuthShell>;
}

export function ResetPasswordPage(){
  const location=useLocation();const initial=(location.state??{}) as {email?:string;devCode?:string};const [email,setEmail]=useState(initial.email??'');const [code,setCode]=useState(initial.devCode??'');const [password,setPassword]=useState('');const [done,setDone]=useState(false);const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  const submit=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError('');try{await api('/auth/reset-password',{method:'POST',body:JSON.stringify({email,code,password})});setDone(true);}catch(err){setError(err instanceof Error?err.message:'Reset failed.');}finally{setBusy(false)}};
  return <AuthShell eyebrow="Choose a new password" title={done?'Password updated':'Secure your business'} subtitle={done?'Your business workspace is ready.':'Enter the reset code and choose a unique password.'}>{done?<div className="auth-result"><CheckCircle2 size={44}/><Link className="button" to="/login">Sign in</Link></div>:<form className="auth-form" onSubmit={submit}>{error&&<Notice kind="error">{error}</Notice>}<Field label="Business email"><Input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></Field><Field label="Reset code"><Input value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,'').slice(0,6))} inputMode="numeric" pattern="[0-9]{6}" autoComplete="one-time-code" required/></Field><Field label="New password" hint="At least 10 characters with upper, lower, and a number."><PasswordInput value={password} onChange={setPassword} autoComplete="new-password"/></Field><Button disabled={busy||code.length!==6}>{busy?'Updating…':<><KeyRound size={17}/> Update password</>}</Button></form>}</AuthShell>;
}
