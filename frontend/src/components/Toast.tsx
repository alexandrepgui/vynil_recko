import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

type ToastType = 'success' | 'error';

interface Toast {
  id: number;
  message: string;
  type: ToastType;
  removing: boolean;
}

interface ToastContextValue {
  showToast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 0;

const TOAST_DURATION = 3000;
const FADE_OUT_DURATION = 300;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    return () => {
      timersRef.current.forEach(clearTimeout);
    };
  }, []);

  const removeToast = useCallback((id: number) => {
    // Start fade-out
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, removing: true } : t)));
    // Remove from DOM after animation
    const timer = setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, FADE_OUT_DURATION);
    timersRef.current.push(timer);
  }, []);

  const showToast = useCallback(
    (message: string, type: ToastType = 'success') => {
      const id = nextId++;
      setToasts((prev) => [...prev, { id, message, type, removing: false }]);
      const timer = setTimeout(() => removeToast(id), TOAST_DURATION);
      timersRef.current.push(timer);
    },
    [removeToast],
  );

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {createPortal(
        <div className="toast-container" aria-live="polite">
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className={`toast toast-${toast.type}${toast.removing ? ' toast-removing' : ''}`}
            >
              {toast.message}
            </div>
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return ctx;
}
