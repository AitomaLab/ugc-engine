import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** Forward billing POSTs to ugc_backend (avoids ad-blockers on /api/stripe/* paths). */
export async function POST(request: NextRequest, backendPath: string) {
  try {
    const auth = request.headers.get('Authorization');
    const contentType = request.headers.get('Content-Type');
    const uiLanguage = request.headers.get('X-Ui-Language');
    const projectId = request.headers.get('X-Project-Id');
    const skipScope = request.headers.get('X-Skip-Project-Scope');

    const body = await request.text();

    const headers: Record<string, string> = {};
    if (auth) headers.Authorization = auth;
    if (contentType) headers['Content-Type'] = contentType;
    if (uiLanguage) headers['X-Ui-Language'] = uiLanguage;
    if (projectId) headers['X-Project-Id'] = projectId;
    if (skipScope) headers['X-Skip-Project-Scope'] = skipScope;

    const res = await fetch(`${BACKEND_URL}${backendPath}`, {
      method: 'POST',
      headers,
      body: body || undefined,
    });

    const text = await res.text();
    let payload: unknown = {};
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = { detail: text };
      }
    }

    return NextResponse.json(payload, { status: res.status });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : 'Billing proxy error' },
      { status: 502 },
    );
  }
}
