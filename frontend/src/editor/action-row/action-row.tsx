import {PlayerRef} from '@remotion/player';
import React from 'react';
import {
	FEATURE_CANVAS_ZOOM_CONTROLS,
	FEATURE_DOWNLOAD_STATE,
	FEATURE_LOAD_STATE,
	FEATURE_REDO_BUTTON,
	FEATURE_SAVE_BUTTON,
	FEATURE_UNDO_BUTTON,
} from '../flags';
import {CanvasZoomControls} from './canvas-zoom-controls';
import {DownloadStateButton} from './download-state-button';
import {LoadStateButton} from './load-state-button';
import {RedoButton} from './redo-button';
import {RenderButton} from './render-button';
import {SaveButton} from './save-button';
import {TasksIndicator} from './tasks-indicator/tasks-indicator';
import {ToolSelection} from './tool-selection';
import {UndoButton} from './undo-button';

export const ActionRow: React.FC<{
	playerRef: React.RefObject<PlayerRef | null>;
}> = ({playerRef}) => {
	return (
		<div className="border-b-editor-starter-border bg-editor-starter-panel flex w-full items-center border-b p-3">
			<div data-toolbar="main" className="flex items-center">
				<ToolSelection playerRef={playerRef} />
				<div data-toolbar-separator="group" className="w-px h-5 bg-white/20 mx-3"></div>
				{FEATURE_UNDO_BUTTON && <UndoButton />}
				{FEATURE_REDO_BUTTON && <RedoButton />}
				{FEATURE_SAVE_BUTTON && <SaveButton />}
				{FEATURE_DOWNLOAD_STATE && <DownloadStateButton />}
				{FEATURE_LOAD_STATE && <LoadStateButton />}
				<div data-toolbar-separator="group" className="w-px h-5 bg-white/20 mx-3"></div>
				<RenderButton />
			</div>
			<div className="ml-4">
				<TasksIndicator />
			</div>
			<div className="flex-1"></div>
			{FEATURE_CANVAS_ZOOM_CONTROLS ? <CanvasZoomControls /> : null}
		</div>
	);
};
