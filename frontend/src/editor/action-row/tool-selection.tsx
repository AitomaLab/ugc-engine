import {PlayerRef} from '@remotion/player';
import Link from 'next/link';
import React, {useCallback, useContext, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
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

/**
 * ImportDropdown - Combines Image, Video, and Audio import options
 * Uses fixed positioning to avoid being clipped by toolbar overflow
 */
const ImportDropdown: React.FC<{
	onImportImage: () => void;
	onImportVideo: () => void;
	onImportAudio: () => void;
}> = ({onImportImage, onImportVideo, onImportAudio}) => {
	const [isOpen, setIsOpen] = useState(false);
	const dropdownMenuRef = useRef<HTMLDivElement>(null);
	const buttonRef = useRef<HTMLButtonElement>(null);
	const [dropdownPosition, setDropdownPosition] = useState({top: 0, left: 0});

	// Calculate dropdown position based on button location
	const updateDropdownPosition = useCallback(() => {
		if (buttonRef.current) {
			const rect = buttonRef.current.getBoundingClientRect();
			setDropdownPosition({
				top: rect.bottom + 4,
				left: rect.left,
			});
		}
	}, []);

	// Update position when dropdown opens
	React.useEffect(() => {
		if (isOpen) {
			updateDropdownPosition();
			window.addEventListener('scroll', updateDropdownPosition, true);
			window.addEventListener('resize', updateDropdownPosition);
			return () => {
				window.removeEventListener('scroll', updateDropdownPosition, true);
				window.removeEventListener('resize', updateDropdownPosition);
			};
		}
	}, [isOpen, updateDropdownPosition]);

	// Close dropdown when clicking outside
	React.useEffect(() => {
		const handleClickOutside = (event: MouseEvent) => {
			if (
				dropdownMenuRef.current &&
				!dropdownMenuRef.current.contains(event.target as Node) &&
				buttonRef.current &&
				!buttonRef.current.contains(event.target as Node)
			) {
				setIsOpen(false);
			}
		};

		if (isOpen) {
			document.addEventListener('mousedown', handleClickOutside);
			return () => {
				document.removeEventListener('mousedown', handleClickOutside);
			};
		}
	}, [isOpen]);

	const handleImportImage = useCallback(() => {
		onImportImage();
		setIsOpen(false);
	}, [onImportImage]);

	const handleImportVideo = useCallback(() => {
		onImportVideo();
		setIsOpen(false);
	}, [onImportVideo]);

	const handleImportAudio = useCallback(() => {
		onImportAudio();
		setIsOpen(false);
	}, [onImportAudio]);

	return (
		<div className="relative">
			{/* Main Import Button */}
			<button
				ref={buttonRef}
				data-toolbar-btn
				onClick={() => {
					setIsOpen(!isOpen);
					if (!isOpen) {
						setTimeout(updateDropdownPosition, 0);
					}
				}}
				className="editor-starter-focus-ring flex h-[34px] items-center justify-center gap-2 rounded-md px-4 text-sm font-medium text-white transition-colors hover:bg-white/10 data-[active=true]:bg-white/15"
				title="Import media"
				aria-label="Import media"
				aria-expanded={isOpen}
				aria-haspopup="menu"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					strokeWidth="2"
					className="h-4 w-4"
				>
					<path d="M12 5v14M5 12h14" />
				</svg>
				<span>Import</span>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					strokeWidth="2"
					className={`h-3.5 w-3.5 transition-transform ${
						isOpen ? 'rotate-180' : ''
					}`}
				>
					<path d="M6 9l6 6 6-6" />
				</svg>
			</button>

			{/* Dropdown Menu */}
			{isOpen
				? createPortal(
						<div
							ref={dropdownMenuRef}
							className="editor-dropdown-menu fixed z-[9999]"
							style={{
								top: `${dropdownPosition.top}px`,
								left: `${dropdownPosition.left}px`,
							}}
							role="menu"
						>
							{/* Image Option */}
							<button
								onClick={handleImportImage}
								className="editor-dropdown-item"
								role="menuitem"
								title="Import image files"
							>
								<span className="editor-dropdown-item-main">
									<ImageIcon className="h-4 w-4" />
									<span>Image</span>
								</span>
							</button>

							{/* Video Option */}
							<button
								onClick={handleImportVideo}
								className="editor-dropdown-item"
								role="menuitem"
								title="Import video files"
							>
								<span className="editor-dropdown-item-main">
									<VideoIcon className="h-4 w-4" />
									<span>Video</span>
								</span>
							</button>

							{/* Audio Option */}
							<button
								onClick={handleImportAudio}
								className="editor-dropdown-item"
								role="menuitem"
								title="Import audio files"
							>
								<span className="editor-dropdown-item-main">
									<AudioIcon className="h-4 w-4" />
									<span>Audio</span>
								</span>
							</button>
						</div>,
						document.body,
					)
				: null}
		</div>
	);
};

/**
 * ToolSelection renders in two modes controlled by props:
 * - renderHomeAndSeparator: renders ONLY the Home button (for left section)
 * - renderTools: renders ONLY the tool buttons (for center section)
 * If neither is passed, renders everything (legacy).
 */
export const ToolSelection: React.FC<{
	playerRef: React.RefObject<PlayerRef | null>;
	renderHomeAndSeparator?: boolean;
	renderImportOnly?: boolean;
	renderTools?: boolean;
}> = ({playerRef, renderHomeAndSeparator, renderImportOnly, renderTools}) => {
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
			e.target.value = '';
		},
		[playerRef, stateAsRef, timelineWriteContext],
	);

	// ─── Mode: Home button only (left section) ───
	if (renderHomeAndSeparator) {
		return (
			<Link
				href="/"
				title="Back to Dashboard"
				aria-label="Back to Dashboard"
				className="editor-starter-focus-ring flex h-8 w-8 items-center justify-center rounded-full bg-white shadow-sm transition-transform hover:scale-105"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="black"
					className="h-4 w-4"
				>
					<path d="M11.47 3.841a.75.75 0 0 1 1.06 0l8.69 8.69a.75.75 0 1 0 1.06-1.061l-8.689-8.69a2.25 2.25 0 0 0-3.182 0l-8.69 8.69a.75.75 0 1 0 1.061 1.06l8.69-8.689Z" />
					<path d="m12 5.432 8.159 8.159c.03.03.06.058.091.086v6.198c0 1.035-.84 1.875-1.875 1.875H15a.75.75 0 0 1-.75-.75v-4.5a.75.75 0 0 0-.75-.75h-3a.75.75 0 0 0-.75.75V21a.75.75 0 0 1-.75.75H5.625a1.875 1.875 0 0 1-1.875-1.875v-6.198a2.29 2.29 0 0 0 .091-.086L12 5.432Z" />
				</svg>
			</Link>
		);
	}

	// ─── Mode: Tool buttons only (center section) ───
	if (renderImportOnly) {
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
				{FEATURE_IMPORT_ASSETS_TOOL ? (
					<ImportDropdown
						onImportImage={addImage}
						onImportVideo={addVideo}
						onImportAudio={addAudio}
					/>
				) : null}
			</>
		);
	}

	// ─── Mode: Tool buttons only (center section) ───
	if (renderTools) {
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
					className="editor-starter-focus-ring flex h-10 items-center justify-center gap-1.5 rounded px-3 text-white transition-colors hover:bg-white/10 data-[active=true]:bg-white/10"
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
						className="editor-starter-focus-ring flex h-10 items-center justify-center gap-1.5 rounded px-3 text-white transition-colors hover:bg-white/10 data-[active=true]:bg-white/10"
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
						className="editor-starter-focus-ring flex h-10 items-center justify-center gap-1.5 rounded px-3 text-white transition-colors hover:bg-white/10 data-[active=true]:bg-white/10"
						title="Add Text"
						aria-label="Add Text"
					>
						<TextIcon className="w-4" />
						<span className="text-xs">Text</span>
					</button>
				) : null}

			</>
		);
	}

	// ─── Legacy: render everything (fallback) ───
	return (
		<>
			<Link
				href="/"
				title="Back to Dashboard"
				aria-label="Back to Dashboard"
				className="editor-starter-focus-ring mr-3 flex h-8 w-8 items-center justify-center rounded-full bg-white shadow-sm transition-transform hover:scale-105"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="black"
					className="h-4 w-4"
				>
					<path d="M11.47 3.841a.75.75 0 0 1 1.06 0l8.69 8.69a.75.75 0 1 0 1.06-1.061l-8.689-8.69a2.25 2.25 0 0 0-3.182 0l-8.69 8.69a.75.75 0 1 0 1.061 1.06l8.69-8.689Z" />
					<path d="m12 5.432 8.159 8.159c.03.03.06.058.091.086v6.198c0 1.035-.84 1.875-1.875 1.875H15a.75.75 0 0 1-.75-.75v-4.5a.75.75 0 0 0-.75-.75h-3a.75.75 0 0 0-.75.75V21a.75.75 0 0 1-.75.75H5.625a1.875 1.875 0 0 1-1.875-1.875v-6.198a2.29 2.29 0 0 0 .091-.086L12 5.432Z" />
				</svg>
			</Link>
			<button
				data-toolbar-btn
				data-active={editMode === 'select'}
				className="editor-starter-focus-ring flex h-10 items-center justify-center gap-1.5 rounded px-3 text-white transition-colors hover:bg-white/10 data-[active=true]:bg-white/10"
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
		</>
	);
};
