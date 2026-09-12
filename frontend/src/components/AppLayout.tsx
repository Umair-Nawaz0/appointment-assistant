import { CalendarDays, ChevronDown, Clock3, ContactRound, LayoutDashboard, LogOut, Menu, MessageSquareText, RadioTower, Settings2, Store, X } from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const links=[
  {to:'/',label:'Overview',icon:LayoutDashboard,end:true},
  {to:'/appointments',label:'Appointments',icon:CalendarDays},
  {to:'/customers',label:'Customers',icon:ContactRound},
  {to:'/conversations',label:'Conversations',icon:MessageSquareText},
  {to:'/business',label:'Business profile',icon:Store},
  {to:'/settings',label:'Booking settings',icon:Settings2},
  {to:'/availability',label:'Availability',icon:Clock3},
  {to:'/channels',label:'Channels',icon:RadioTower},
];

export function AppLayout() {
  const {business,logout}=useAuth(); const navigate=useNavigate(); const [open,setOpen]=useState(false);
  const signOut=async()=>{await logout();navigate('/login');};
  return <div className="app-shell">
    <button className="mobile-menu" onClick={()=>setOpen(!open)} aria-label="Toggle navigation">{open?<X/>:<Menu/>}</button>
    <aside className={`sidebar ${open?'sidebar-open':''}`}>
      <div className="brand"><span className="brand-mark">A</span><div><strong>Appointment</strong><small>Assistant</small></div></div>
      <nav>{links.map(({to,label,icon:Icon,end})=><NavLink key={to} to={to} end={end} onClick={()=>setOpen(false)}><Icon size={19}/><span>{label}</span></NavLink>)}</nav>
      <button className="account" onClick={signOut}><span className="avatar">{business?.businessName?.[0]?.toUpperCase()}</span><span><strong>{business?.businessName}</strong><small>{business?.email}</small></span><LogOut size={17}/></button>
    </aside>
    <main className="main"><div className="topbar"><div><small>Workspace</small><strong>{business?.businessName}</strong></div><ChevronDown size={17}/></div><div className="content"><Outlet/></div></main>
  </div>;
}
