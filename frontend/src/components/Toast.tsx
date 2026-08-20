import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type ToastKind = "success" | "warning" | "danger";

interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}

type PushToast = (kind: ToastKind, message: string) => void;

const ToastContext = createContext<PushToast>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback<PushToast>((kind, message) => {
    const id = Date.now() + Math.random();
    setItems((current) => [...current, { id, kind, message }]);
    window.setTimeout(() => {
      setItems((current) => current.filter((item) => item.id !== id));
    }, 2600);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-host" role="status" aria-live="polite">
        {items.map((item) => (
          <div
            key={item.id}
            className={`toast card p-3 text-sm ${
              item.kind === "success"
                ? "text-success"
                : item.kind === "danger"
                  ? "text-destructive"
                  : "text-warning"
            }`}
          >
            <span className="flex-1">{item.message}</span>
            <span className="toast-progress" />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): PushToast {
  return useContext(ToastContext);
}
