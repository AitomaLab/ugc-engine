import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { renderId, bucketName } = body;

    if (!renderId) {
      return NextResponse.json({ error: 'renderId is required' }, { status: 400 });
    }

    const token = request.cookies.get('sb-access-token')?.value
      || request.headers.get('Authorization')?.replace('Bearer ', '');

    const res = await fetch(`${BACKEND_URL}/api/editor/render/${renderId}/progress`, {
      method: 'GET',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!res.ok) {
      const err = await res.text();
      return NextResponse.json({ error: err }, { status: res.status });
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { type: 'error', error: error instanceof Error ? error.message : 'Progress check failed' },
      { status: 500 }
    );
  }
}
