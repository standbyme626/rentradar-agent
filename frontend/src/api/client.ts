export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`${response.status} ${body.slice(0, 200)}`)
  }
  return response.json() as Promise<T>
}
