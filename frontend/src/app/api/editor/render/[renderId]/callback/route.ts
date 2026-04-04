import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Proxy callback from Modal to the FastAPI backend.
 * Modal calls: POST /api/editor/render/{renderId}/callback
 * This forwards to: POST {BACKEND_URL}/api/editor/render/{renderId}/callback
 *
 * No auth required — this is a server-to-server callback.
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ renderId: string }> }
) {
  try {
    const { renderId } = await params;
    const body = await request.json();

    const res = await fetch(
      `${BACKEND_URL}/api/editor/render/${renderId}/callback`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }
    );

    if (!res.ok) {
      const err = await res.text();
      return NextResponse.json({ error: err }, { status: res.status });
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('[callback proxy] error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Callback proxy failed' },
      { status: 500 }
    );
  }
}
