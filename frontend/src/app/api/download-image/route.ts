import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
    const url = request.nextUrl.searchParams.get('url');
    if (!url) {
        return NextResponse.json({ error: 'Missing url parameter' }, { status: 400 });
    }

    let parsed: URL;
    try {
        parsed = new URL(url);
    } catch {
        return NextResponse.json({ error: 'Invalid url' }, { status: 400 });
    }
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        return NextResponse.json({ error: 'Unsupported protocol' }, { status: 400 });
    }

    try {
        const upstream = await fetch(parsed.toString());
        if (!upstream.ok || !upstream.body) {
            return NextResponse.json(
                { error: `Upstream ${upstream.status}` },
                { status: 502 },
            );
        }
        const contentType = upstream.headers.get('content-type') || 'application/octet-stream';
        if (!contentType.startsWith('image/') && !contentType.startsWith('video/')) {
            return NextResponse.json({ error: 'Unsupported content type' }, { status: 400 });
        }

        return new NextResponse(upstream.body, {
            status: 200,
            headers: {
                'Content-Type': contentType,
                'Cache-Control': 'private, max-age=0',
            },
        });
    } catch (err) {
        return NextResponse.json(
            { error: err instanceof Error ? err.message : 'Fetch failed' },
            { status: 502 },
        );
    }
}
