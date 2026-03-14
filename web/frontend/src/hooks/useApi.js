import { useState, useEffect } from "react";

const API = "http://127.0.0.1:8000";

export function useApi(path, opts = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const { enabled = true, deps = [] } = opts;

  useEffect(() => {
    if (!enabled) return;
    setLoading(true);
    fetch(`${API}${path}`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [path, enabled, ...deps]);

  return { data, loading, error };
}

export async function fetchApi(path) {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}
