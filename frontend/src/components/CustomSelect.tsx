import { useEffect, useRef, useState } from 'react';

interface Option {
  value: string;
  label: string;
}

interface CustomSelectProps {
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  disabled?: boolean;
  title?: string;
  className?: string;
}

export default function CustomSelect({ value, options, onChange, disabled, title, className }: CustomSelectProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const selected = options.find((o) => o.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open]);

  return (
    <div className={`cselect${disabled ? ' cselect-disabled' : ''} ${className ?? ''}`} ref={ref} title={title}>
      <button
        className={`cselect-trigger${open ? ' cselect-open' : ''}`}
        onClick={() => !disabled && setOpen((v) => !v)}
        type="button"
        disabled={disabled}
      >
        <span className="cselect-value">{selected?.label ?? ''}</span>
        <svg className="cselect-chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>
      {open && (
        <div className="cselect-menu">
          {options.map((opt) => (
            <button
              key={opt.value}
              className={`cselect-option${opt.value === value ? ' cselect-option-active' : ''}`}
              onClick={() => { onChange(opt.value); setOpen(false); }}
              type="button"
            >
              {opt.label}
              {opt.value === value && (
                <svg className="cselect-check" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
