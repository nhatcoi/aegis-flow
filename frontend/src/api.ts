export async function api<T>(path: string, body?: unknown, method = 'POST'): Promise<T> {
  const response = await fetch(`/api${path}`, body === undefined ? {} : {
    method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    const detail = payload.detail;
    throw new Error(Array.isArray(detail) ? detail.map((e: {loc: string[]; msg: string}) => `${e.loc.join('.')}: ${e.msg}`).join('\n') : detail || 'Không thể kết nối máy chủ');
  }
  return payload as T;
}
