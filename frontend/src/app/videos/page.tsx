import { redirect } from 'next/navigation';

/** Legacy video library — bare /videos redirects via middleware; this catches edge cases. */
export default function VideosPage() {
    redirect('/projects');
}
