import {PlayerRef} from '@remotion/player';
import React, {useCallback, useContext} from 'react';
import {addAsset} from '../assets/add-asset';
import {EditModeContext} from '../edit-mode';
import {
	FEATURE_CREATE_TEXT_TOOL,
	FEATURE_DRAW_SOLID_TOOL,
	FEATURE_IMPORT_ASSETS_TOOL,
} from '../flags';
import {AudioIcon} from '../icons/audio-icon';
import {EditModeIcon} from '../icons/edit-mode';
import {ImageIcon} from '../icons/image';
import {SolidIcon} from '../icons/solid';
import {TextIcon} from '../icons/text';
import {VideoIcon} from '../icons/video';
import {useCurrentStateAsRef, useWriteContext} from '../utils/use-context';

export const ToolSelection: React.FC<{
	playerRef: React.RefObject<PlayerRef | null>;
}> = ({playerRef}) => {
	const timelineWriteContext = useWriteContext();
	const {editMode, setEditMode} = useContext(EditModeContext);

	const setSelectEditMode = useCallback(() => {
		setEditMode('select');
	}, [setEditMode]);

	const setSolidEditMode = useCallback(() => {
		setEditMode('draw-solid');
	}, [setEditMode]);

	const setCreateTextMode = useCallback(() => {
		setEditMode('create-text');
	}, [setEditMode]);

	const imageInputRef = React.useRef<HTMLInputElement>(null);
	const videoInputRef = React.useRef<HTMLInputElement>(null);
	const audioInputRef = React.useRef<HTMLInputElement>(null);

	const addImage = useCallback(() => {
		imageInputRef.current?.click();
	}, []);

	const addVideo = useCallback(() => {
		videoInputRef.current?.click();
	}, []);

	const addAudio = useCallback(() => {
		audioInputRef.current?.click();
	}, []);

	const stateAsRef = useCurrentStateAsRef();

	const handleFileChange = useCallback(
		async (e: React.ChangeEvent<HTMLInputElement>) => {
			const files = e.target.files;
			if (!files) return;

			const uploadPromises = [];
			for (const file of files) {
				uploadPromises.push(
					addAsset({
						file,
						timelineWriteContext: timelineWriteContext,
						playerRef,
						dropPosition: null,
						fps: stateAsRef.current.undoableState.fps,
						compositionWidth: stateAsRef.current.undoableState.compositionWidth,
						compositionHeight:
							stateAsRef.current.undoableState.compositionHeight,
						tracks: stateAsRef.current.undoableState.tracks,
						filename: file.name,
					}),
				);
			}
			await Promise.all(uploadPromises);
			// Allow for more files to be added
			e.target.value = '';
		},
		[playerRef, stateAsRef, timelineWriteContext],
	);
	return (
		<>
			<input
				ref={imageInputRef}
				type="file"
				accept="image/*"
				onChange={handleFileChange}
				className="hidden"
				multiple
			/>
			<input
				ref={videoInputRef}
				type="file"
				accept="video/*"
				onChange={handleFileChange}
				className="hidden"
				multiple
			/>
			<input
				ref={audioInputRef}
				type="file"
				accept="audio/*"
				onChange={handleFileChange}
				className="hidden"
				multiple
			/>
			<button
				data-toolbar-btn
				data-active={editMode === 'select'}
				className="editor-starter-focus-ring flex h-10 items-center justify-center gap-1.5 px-3 rounded text-white transition-colors hover:bg-white/10 data-[active=true]:bg-white/10"
				title="Select"
				onClick={setSelectEditMode}
				aria-label="Select"
			>
				<EditModeIcon
					fill="none"
					stroke="currentColor"
					strokeWidth="2"
					className="w-4"
				/>
				<span className="text-xs">Select</span>
			</button>

			{FEATURE_DRAW_SOLID_TOOL ? (
				<button
					data-toolbar-btn
					onClick={setSolidEditMode}
					data-active={editMode === 'draw-solid'}
					className="editor-starter-focus-ring flex h-10 items-center justify-center gap-1.5 px-3 rounded text-white transition-colors hover:bg-white/10 data-[active=true]:bg-white/10"
					title="Add Shape"
					aria-label="Add Shape"
				>
					<SolidIcon className="w-4" />
					<span className="text-xs">Shape</span>
				</button>
			) : null}
			{FEATURE_CREATE_TEXT_TOOL ? (
				<button
					data-toolbar-btn
					onClick={setCreateTextMode}
					data-active={editMode === 'create-text'}
					className="editor-starter-focus-ring flex h-10 items-center justify-center gap-1.5 px-3 rounded text-white transition-colors hover:bg-white/10 data-[active=true]:bg-white/10"
					title="Add Text"
					aria-label="Add Text"
				>
					<TextIcon className="w-4" />
					<span className="text-xs">Text</span>
				</button>
			) : null}
			{FEATURE_IMPORT_ASSETS_TOOL ? (
				<>
					<button
						data-toolbar-btn
						onClick={addImage}
						className="editor-starter-focus-ring flex h-10 items-center justify-center gap-1.5 px-3 rounded text-white transition-colors hover:bg-white/10"
						title="Add Image"
						aria-label="Add Image"
					>
						<ImageIcon />
						<span className="text-xs">Image</span>
					</button>
					<button
						data-toolbar-btn
						onClick={addVideo}
						className="editor-starter-focus-ring flex h-10 items-center justify-center gap-1.5 px-3 rounded text-white transition-colors hover:bg-white/10"
						title="Add Video"
						aria-label="Add Video"
					>
						<VideoIcon />
						<span className="text-xs">Video</span>
					</button>
					<button
						data-toolbar-btn
						onClick={addAudio}
						className="editor-starter-focus-ring flex h-10 items-center justify-center gap-1.5 px-3 rounded text-white transition-colors hover:bg-white/10"
						title="Add Audio"
						aria-label="Add Audio"
					>
						<AudioIcon />
						<span className="text-xs">Audio</span>
					</button>
				</>
			) : null}
		</>
	);
};
