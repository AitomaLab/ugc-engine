import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const token = request.cookies.get('sb-access-token')?.value
      || request.headers.get('Authorization')?.replace('Bearer ', '');

    const res = await fetch(`${BACKEND_URL}/api/editor/upload-url`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        filename: body.contentType ? `upload.${body.contentType.split('/')[1]}` : 'upload.bin',
        contentType: body.contentType || 'application/octet-stream',
        size: body.size || 0,
      }),
    });

    if (!res.ok) {
      const err = await res.text();
      return NextResponse.json({ error: err }, { status: res.status });
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Upload URL request failed' },
      { status: 500 }
    );
  }
}
