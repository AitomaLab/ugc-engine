/**
 * Aitoma: the editor is always mounted at /editor/[jobId], and the job id is
 * not otherwise threaded through the Editor Starter's state.
 */
export const getJobIdFromUrl = (): string => {
	if (typeof window === 'undefined') {
		return '';
	}
	const pathParts = window.location.pathname.split('/');
	return pathParts[pathParts.indexOf('editor') + 1] || '';
};
