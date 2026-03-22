import { useState, useCallback } from 'react';
import { apiFetch } from '../api';

export default function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const request = useCallback(async (path, options = {}) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch(path, options);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const get = useCallback((path) => request(path), [request]);

  const post = useCallback(
    (path, body) =>
      request(path, { method: 'POST', body: JSON.stringify(body) }),
    [request]
  );

  const put = useCallback(
    (path, body) =>
      request(path, { method: 'PUT', body: JSON.stringify(body) }),
    [request]
  );

  const del = useCallback(
    (path) => request(path, { method: 'DELETE' }),
    [request]
  );

  return { loading, error, get, post, put, del, request };
}
