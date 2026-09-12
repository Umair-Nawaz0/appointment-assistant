import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';

export function Card({ children, className='' }: {children:ReactNode;className?:string}) { return <section className={`card ${className}`}>{children}</section>; }
export function PageHeader({ title, description, action }: {title:string;description:string;action?:ReactNode}) {
  return <header className="page-header"><div><h1>{title}</h1><p>{description}</p></div>{action}</header>;
}
export function Field({ label, hint, children }: {label:string;hint?:string;children:ReactNode}) {
  return <label className="field"><span>{label}</span>{children}{hint&&<small>{hint}</small>}</label>;
}
export function Input(props:InputHTMLAttributes<HTMLInputElement>) { return <input className="input" {...props}/>; }
export function Select(props:SelectHTMLAttributes<HTMLSelectElement>) { return <select className="input" {...props}/>; }
export function Textarea(props:TextareaHTMLAttributes<HTMLTextAreaElement>) { return <textarea className="input textarea" {...props}/>; }
export function Button({ className='', ...props }:ButtonHTMLAttributes<HTMLButtonElement>) { return <button className={`button ${className}`} {...props}/>; }
export function Badge({ children, tone='neutral' }: {children:ReactNode;tone?:'green'|'amber'|'blue'|'red'|'neutral'}) { return <span className={`badge badge-${tone}`}>{children}</span>; }
export function Notice({ children, kind='success' }: {children:ReactNode;kind?:'success'|'error'|'info'}) { return <div className={`notice notice-${kind}`}>{children}</div>; }
export function Empty({ title, text }: {title:string;text:string}) { return <div className="empty"><strong>{title}</strong><p>{text}</p></div>; }
export function Spinner() { return <div className="spinner" aria-label="Loading"/>; }
