const useMock = (import.meta.env.VITE_USE_MOCK ?? 'true') !== 'false'

export const apiConfig = {
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? '/api',
  useMock,
  useMockAgent: (import.meta.env.VITE_USE_MOCK_AGENT ?? (useMock ? 'true' : 'false')) !== 'false',
  useMockAdmin: (import.meta.env.VITE_USE_MOCK_ADMIN ?? (useMock ? 'true' : 'false')) !== 'false',
  amapJsKey: import.meta.env.VITE_AMAP_JS_KEY ?? '',
  amapSecurityCode: import.meta.env.VITE_AMAP_SECURITY_CODE ?? '',
}
