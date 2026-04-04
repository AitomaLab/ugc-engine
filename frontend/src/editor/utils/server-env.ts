/**
 * server-env.ts — Aitoma Integration
 * Lambda rendering is replaced by the Python backend.
 * This file is stubbed to remove all Lambda and Zod dependencies.
 */

type ServerEnv = {
	OPENAI_API_KEY?: string;
};

let _cachedServerEnv: ServerEnv | null = null;

export const requireServerEnv = (): ServerEnv => {
	if (_cachedServerEnv) {
		return _cachedServerEnv;
	}
	_cachedServerEnv = {
		OPENAI_API_KEY: typeof process !== 'undefined' ? process.env?.OPENAI_API_KEY : undefined,
	};
	return _cachedServerEnv;
};
