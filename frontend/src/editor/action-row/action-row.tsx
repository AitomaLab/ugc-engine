import {PlayerRef} from '@remotion/player';
import React from 'react';
import {
	FEATURE_AI_AGENT,
	FEATURE_CANVAS_ZOOM_CONTROLS,
	FEATURE_REDO_BUTTON,
	FEATURE_UNDO_BUTTON,
} from '../flags';
import {AiAgentButton} from './ai-agent-button';
import {CanvasZoomControls} from './canvas-zoom-controls';
import {FileMenu} from './file-menu';
import {InspectorToggleButton} from './inspector-toggle-button';
import {RedoButton} from './redo-button';
import {RenderButton} from './render-button';
import {TasksIndicator} from './tasks-indicator/tasks-indicator';
import {ToolSelection} from './tool-selection';
import {UndoButton} from './undo-button';

export const ActionRow: React.FC<{
	playerRef: React.RefObject<PlayerRef | null>;
	sidebarOpen: boolean;
	onToggleSidebar: () => void;
	inspectorOpen: boolean;
	onToggleInspector: () => void;
}> = ({playerRef, sidebarOpen, onToggleSidebar, inspectorOpen, onToggleInspector}) => {
	return (
		<div
			data-editor-toolbar
			className="border-b-editor-starter-border bg-editor-starter-panel flex w-full items-center border-b"
		>
			<div data-toolbar-section="left" className="flex items-center">
				<ToolSelection playerRef={playerRef} renderHomeAndSeparator />
				<FileMenu />
				<ToolSelection playerRef={playerRef} renderImportOnly />
			</div>

			<div data-toolbar-section="center" className="flex flex-1 items-center justify-center">
				<div data-toolbar="main" className="flex items-center">
					<ToolSelection playerRef={playerRef} renderTools />
					<div data-toolbar-separator="group" className="mx-3 h-5 w-px bg-white/20" />
					{FEATURE_UNDO_BUTTON && <UndoButton />}
					{FEATURE_REDO_BUTTON && <RedoButton />}
					<div data-toolbar-separator="group" className="mx-3 h-5 w-px bg-white/20" />
					<TasksIndicator />
					{FEATURE_CANVAS_ZOOM_CONTROLS ? <CanvasZoomControls /> : null}
				</div>
			</div>

			<div data-toolbar-section="right" className="flex items-center gap-2 pr-3">
				<InspectorToggleButton open={inspectorOpen} onToggle={onToggleInspector} />
				{FEATURE_AI_AGENT ? (
					<AiAgentButton open={sidebarOpen} onToggle={onToggleSidebar} />
				) : null}
				<RenderButton />
			</div>
		</div>
	);
};
