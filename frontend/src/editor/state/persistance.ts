import {AssetState} from '../assets/assets';
import {FEATURE_SAVE_BUTTON} from '../flags';
import {hasAssetsWithErrors} from '../utils/asset-status-utils';
import {hasUploadingAssets} from '../utils/upload-status';
import {UndoableState} from './types';

const BASE_KEY = 'remotion-editor-starter-state-v3';

/**
 * Get a job-specific localStorage key.
 * When editing /editor/{jobId}, each job gets its own saved state
 * so opening a different video never loads stale data.
 */
const getKey = (): string => {
	if (typeof window === 'undefined') return BASE_KEY;
	const match = window.location.pathname.match(/\/editor\/([^/]+)/);
	return match ? `${BASE_KEY}:${match[1]}` : BASE_KEY;
};

export const loadState = (): UndoableState | null => {
	if (!FEATURE_SAVE_BUTTON) {
		throw new Error('Save button feature flag is disabled');
	}

	if (typeof localStorage === 'undefined') {
		return null;
	}

	const jobKey = getKey();
	const state = localStorage.getItem(jobKey);
	if (!state) {
		return null;
	}

	return JSON.parse(state);
};

export const saveState = (
	state: UndoableState,
	assetStatus: Record<string, AssetState>,
) => {
	if (!FEATURE_SAVE_BUTTON) {
		throw new Error('Save button feature flag is disabled');
	}

	const assetsUploading = hasUploadingAssets(assetStatus);
	if (assetsUploading) {
		throw new Error(
			'Cannot save while assets are getting uploaded to the cloud',
		);
	}

	if (hasAssetsWithErrors(assetStatus)) {
		throw new Error(
			'Cannot save: Some assets have errors. Please fix them before saving.',
		);
		return;
	}

	localStorage.setItem(getKey(), JSON.stringify(state));
	// eslint-disable-next-line no-console
	console.log('Saved state to Local Storage.', state);
};
