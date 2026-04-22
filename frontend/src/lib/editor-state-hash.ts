/**
 * UTF-8–safe base64 for putting editor JSON in the URL hash.
 * Plain btoa(JSON.stringify(...)) throws on captions / non-Latin1 text.
 */
export function encodeJsonForUrlHash(data: unknown): string {
	const json = JSON.stringify(data);
	const bytes = new TextEncoder().encode(json);
	let binary = '';
	for (let i = 0; i < bytes.length; i++) {
		binary += String.fromCharCode(bytes[i]);
	}
	return btoa(binary);
}

export function decodeJsonFromUrlHash<T = unknown>(base64: string): T {
	const binary = atob(base64);
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i++) {
		bytes[i] = binary.charCodeAt(i);
	}
	const json = new TextDecoder('utf-8').decode(bytes);
	return JSON.parse(json) as T;
}
