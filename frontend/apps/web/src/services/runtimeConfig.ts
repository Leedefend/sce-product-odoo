declare global {
  interface Window {
    __SC_RUNTIME_CONFIG__?: {
      odooDb?: string;
      odooDbLocked?: boolean;
    };
  }
}

const runtime = typeof window !== 'undefined' ? window.__SC_RUNTIME_CONFIG__ : undefined;

export const runtimeOdooDb = String(runtime?.odooDb || '').trim();
export const runtimeOdooDbLocked = Boolean(runtimeOdooDb && runtime?.odooDbLocked === true);
