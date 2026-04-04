import { NextResponse } from 'next/server';

// Stub: Captioning is disabled in the editor (FEATURE_CAPTIONING = false).
// Captions are injected from the backend via the UndoableState adapter.
export async function POST() {
  return NextResponse.json(
    { error: 'Captioning is handled server-side. This endpoint is disabled.' },
    { status: 400 }
  );
}
