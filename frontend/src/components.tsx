import { useState, type ReactNode, type ButtonHTMLAttributes } from 'react';
import { Check, CircleAlert, Copy, X } from 'lucide-react';
import type { Expr, State } from './types';

export function Button({children, variant = 'secondary', ...props}: ButtonHTMLAttributes<HTMLButtonElement> & {variant?: 'primary'|'secondary'|'ghost'|'danger'}) {
  return <button className={`button ${variant}`} {...props}>{children}</button>;
}
export function Badge({children, tone = 'neutral'}: {children: ReactNode; tone?: 'neutral'|'strong'|'danger'}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function Panel({children, className = ''}: {children: ReactNode; className?: string}) {
  return <section className={`panel ${className}`}>{children}</section>;
}
export function Empty({title, children}: {title: string; children: ReactNode}) {
  return <div className="empty"><span className="empty-icon"><CircleAlert size={24}/></span><h3>{title}</h3><p>{children}</p></div>;
}
export function StateValues({state}: {state: State}) {
  return <dl className="state-values">{Object.entries(state).map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{String(value)}</dd></div>)}</dl>;
}
export function expression(expr: Expr): string {
  if (typeof expr !== 'object') return String(expr);
  const [op, args] = Object.entries(expr)[0];
  const signs: Record<string, string> = {and: ' ∧ ', or: ' ∨ ', eq: ' = ', ne: ' ≠ ', le: ' ≤ ', lt: ' < ', implies: ' ⇒ ', add: ' + ', sub: ' − '};
  if (op === 'not') return `¬${expression(args[0])}`;
  return `(${args.map(expression).join(signs[op] || ` ${op} `)})`;
}
export function Code({source}: {source: string}) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);
  return <div className="code-wrap"><button className="copy-button" aria-label="Sao chép mã" onClick={async () => {
    try { await navigator.clipboard.writeText(source); setCopied(true); setError(false); setTimeout(() => setCopied(false), 1800); }
    catch {setError(true);}
  }}>{copied ? <Check size={15}/> : <Copy size={15}/>} {error ? 'Hãy chọn và sao chép thủ công' : copied ? 'Đã sao chép' : 'Sao chép'}</button><pre className="code"><code>{source}</code></pre></div>;
}
export function Modal({title, children, close}: {title: string; children: ReactNode; close: () => void}) {
  return <div className="modal-backdrop" onClick={close}><section role="dialog" aria-modal="true" aria-label={title} className="modal" onClick={e => e.stopPropagation()} onKeyDown={e => {
    if (e.key === 'Escape') close();
    if (e.key === 'Tab') {
      const elements = e.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), textarea, input, select');
      const first = elements[0], last = elements[elements.length - 1];
      if (e.shiftKey && document.activeElement === first) {e.preventDefault(); last?.focus();}
      else if (!e.shiftKey && document.activeElement === last) {e.preventDefault(); first?.focus();}
    }
  }}><header><h2>{title}</h2><button className="icon-button" aria-label="Đóng trình chỉnh sửa" onClick={close}><X size={20}/></button></header>{children}</section></div>;
}
