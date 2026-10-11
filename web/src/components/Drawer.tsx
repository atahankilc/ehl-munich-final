import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { X } from "lucide-react";

/** Right-hand sheet for detail that shouldn't cost the PM their place (evidence, findings, sources). */
export function Drawer({ open, onClose, title, sub, children, width }: { open: boolean; onClose: () => void; title: ReactNode; sub?: ReactNode; children: ReactNode; width?: number }) {
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="drawer-scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.aside
            className="drawer"
            role="dialog"
            aria-modal="true"
            style={width ? { width: `min(${width}px, calc(100vw - 20px))` } : undefined}
            initial={{ x: 40, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 30, opacity: 0, transition: { duration: 0.16 } }}
            transition={{ duration: 0.34, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="drawer-head">
              <div className="grow">
                <div className="t-title">{title}</div>
                {sub && <div className="muted t-small" style={{ marginTop: 4 }}>{sub}</div>}
              </div>
              <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose} aria-label="Close">
                <X />
              </button>
            </div>
            <div className="drawer-body">{children}</div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>,
    document.body,
  );
}
