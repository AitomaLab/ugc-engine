import {taskIndicatorRef} from '../action-row/tasks-indicator/tasks-indicator';
import {EditorStarterAsset} from '../assets/assets';
import {SetState} from '../context-provider';
import {EditorStarterItem} from '../items/item-type';
import {
	addRenderingTask,
	updateRenderingTask,
} from '../state/actions/set-render-state';
import {TrackType} from '../state/types';
import {editorFetchRender, editorFetchProgress} from '../utils/editor-api';
import {getEditorExportFileName} from '../utils/export-file-name';
import {generateRandomId} from '../utils/generate-random-id';
import {CodecOption} from './codec-selector';
import {
	GetProgressPayload,
	GetProgressResponse,
	RenderVideoPayload,
	RenderVideoResponse,
} from './types';

export type RenderingTaskState =
	| {
			type: 'render-initiated';
	  }
	| {
			type: 'done';
			outputFile: string;
			outputSizeInBytes: number;
			doneAt: number;
	  }
	| {
			type: 'in-progress';
			overallProgress: number;
	  }
	| {
			type: 'error';
			error: string;
	  };

export type RenderingTask = {
	id: string;
	outputName: string;
	status: RenderingTaskState;
	codec: CodecOption;
	durationInSeconds: number;
	startedAt: number;
	type: 'rendering';
};

const getProgress = async ({
	bucketName,
	renderId,
	signal,
	setState,
	taskId,
}: {
	bucketName: string;
	renderId: string;
	signal: AbortSignal;
	setState: SetState;
	taskId: string;
}) => {
	try {
		const payload: GetProgressPayload = {
			bucketName,
			renderId,
		};

		const res = await editorFetchProgress(
			{bucketName, renderId},
			signal,
		);

		const json = (await res.json()) as GetProgressResponse;

		if (json.type === 'done') {
			setState({
				commitToUndoStack: false,
				update: (prevState) => {
					return updateRenderingTask({
						state: prevState,
						taskId,
						newStatus: {
							type: 'done',
							outputFile: json.outputFile,
							outputSizeInBytes: json.outputSizeInBytes,
							doneAt: Date.now(),
						},
					});
				},
			});
			return;
		}

		if (json.type === 'error') {
			setState({
				commitToUndoStack: false,
				update: (prevState) => {
					return updateRenderingTask({
						state: prevState,
						taskId,
						newStatus: {
							type: 'error',
							error: json.error,
						},
					});
				},
			});
			return;
		}

		setState({
			commitToUndoStack: false,
			update: (prevState) => {
				return updateRenderingTask({
					state: prevState,
					taskId,
					newStatus: {
						type: 'in-progress',
						overallProgress: json.overallProgress,
					},
				});
			},
		});

		await new Promise((resolve) => setTimeout(resolve, 250));
		await getProgress({bucketName, renderId, signal, setState, taskId});
	} catch (err) {
		if (err instanceof DOMException && err.name === 'AbortError') {
			return;
		}

		throw err;
	}
};

export const triggerLambdaRender = async ({
	compositionHeight,
	compositionWidth,
	compositionDurationInSeconds,
	tracks,
	setState,
	assets,
	items,
	codec,
}: {
	compositionHeight: number;
	compositionWidth: number;
	compositionDurationInSeconds: number;
	tracks: TrackType[];
	setState: SetState;
	assets: Record<string, EditorStarterAsset>;
	items: Record<string, EditorStarterItem>;
	codec: 'h264' | 'vp8';
}) => {
	const taskId = generateRandomId();
	const controller = new AbortController();

	try {
		setState({
			commitToUndoStack: false,
			update: (prevState) => {
				return addRenderingTask({
					state: prevState,
					task: {
						id: taskId,
						status: {type: 'render-initiated'},
						codec,
						outputName: getEditorExportFileName(codec),
						durationInSeconds: compositionDurationInSeconds,
						startedAt: Date.now(),
						type: 'rendering',
					},
				});
			},
		});
		taskIndicatorRef.current?.open();

		// Aitoma: Extract job_id from the editor URL path (/editor/[jobId])
		const pathParts = window.location.pathname.split('/');
		const jobIdFromUrl = pathParts[pathParts.indexOf('editor') + 1] || '';

		const body: RenderVideoPayload = {
			compositionHeight,
			compositionWidth,
			tracks,
			assets,
			items,
			codec,
		};

		const res = await editorFetchRender({
			job_id: jobIdFromUrl,
			editor_state: body,
			codec,
		});

		if (res.status >= 500) {
			throw new Error(`Error starting render: ${res.status}`);
		}

		const json = (await res.json()) as RenderVideoResponse;

		if (json.type === 'error') {
			throw new Error(`Error starting render: ${json.error}`);
		}

		await getProgress({
			bucketName: json.bucketName,
			renderId: json.renderId,
			signal: controller.signal,
			setState,
			taskId,
		});
	} catch (e) {
		setState({
			update: (prevState) =>
				updateRenderingTask({
					state: prevState,
					taskId,
					newStatus: {
						type: 'error',
						error: e instanceof Error ? e.message : 'Unknown error',
					},
				}),
			commitToUndoStack: false,
		});
	}
};
