'use client';

import React, {useCallback, useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {SaveIcon} from '../icons/save';
import {DownloadIcon} from '../icons/download-state';
import {UploadIcon} from '../icons/upload';
import {
	cleanUpAssetStatus,
	cleanUpStateBeforeSaving,
} from '../state/clean-up-state-before-saving';
import {saveState} from '../state/persistance';
import {EditorState, UndoableState} from '../state/types';
import {hasAssetsWithErrors} from '../utils/asset-status-utils';
import {hasUploadingAssets} from '../utils/upload-status';
import {useFullState, useWriteContext} from '../utils/use-context';
import {toast} from 'sonner';

export const FileMenu: React.FC = () => {
	const [open, setOpen] = useState(false);
	const menuRef = useRef<HTMLDivElement>(null);
	const buttonRef = useRef<HTMLButtonElement>(null);
	const [menuPosition, setMenuPosition] = useState({top: 0, left: 0});
	const state = useFullState();
	const {setState} = useWriteContext();
	const fileInputRef = useRef<HTMLInputElement>(null);

	const updateMenuPosition = useCallback(() => {
		if (!buttonRef.current) {
			return;
		}

		const rect = buttonRef.current.getBoundingClientRect();
		setMenuPosition({
			top: rect.bottom + 4,
			left: rect.left,
		});
	}, []);

	// Close on outside click
	useEffect(() => {
		if (!open) return;
		const handler = (e: MouseEvent) => {
			if (
				menuRef.current &&
				!menuRef.current.contains(e.target as Node) &&
				buttonRef.current &&
				!buttonRef.current.contains(e.target as Node)
			) {
				setOpen(false);
			}
		};
		document.addEventListener('mousedown', handler);
		return () => document.removeEventListener('mousedown', handler);
	}, [open]);

	// Close on Escape
	useEffect(() => {
		if (!open) return;
		const handler = (e: KeyboardEvent) => {
			if (e.key === 'Escape') setOpen(false);
		};
		document.addEventListener('keydown', handler);
		return () => document.removeEventListener('keydown', handler);
	}, [open]);

	useEffect(() => {
		if (!open) {
			return;
		}

		updateMenuPosition();
		window.addEventListener('scroll', updateMenuPosition, true);
		window.addEventListener('resize', updateMenuPosition);
		return () => {
			window.removeEventListener('scroll', updateMenuPosition, true);
			window.removeEventListener('resize', updateMenuPosition);
		};
	}, [open, updateMenuPosition]);

	const assetsUploading = hasUploadingAssets(state.assetStatus);
	const assetsWithErrors = hasAssetsWithErrors(state.assetStatus);

	// Save
	const handleSave = useCallback(() => {
		try {
			const cleanedUpState = cleanUpAssetStatus(state);
			saveState(
				cleanUpStateBeforeSaving(cleanedUpState.undoableState),
				cleanedUpState.assetStatus,
			);
			toast.success('Project saved');
		} catch (error) {
			toast.error(
				error instanceof Error ? error.message : 'An unknown error occurred',
			);
		}
		setOpen(false);
	}, [state]);

	// Backup (download)
	const handleBackup = useCallback(() => {
		try {
			const cleanedUpState = cleanUpAssetStatus(state);
			const stateToDownload = cleanUpStateBeforeSaving(
				cleanedUpState.undoableState,
			);
			const dataStr = JSON.stringify(stateToDownload, null, 2);
			const dataBlob = new Blob([dataStr], {type: 'application/json'});
			const url = URL.createObjectURL(dataBlob);
			const link = document.createElement('a');
			link.href = url;
			link.download = `editor-state-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
			document.body.appendChild(link);
			link.click();
			document.body.removeChild(link);
			URL.revokeObjectURL(url);
			toast.success('State downloaded successfully');
		} catch (error) {
			toast.error(
				error instanceof Error ? error.message : 'Failed to download state',
			);
		}
		setOpen(false);
	}, [state]);

	// Restore (load)
	const handleRestore = useCallback(() => {
		fileInputRef.current?.click();
	}, []);

	const handleFileChange = useCallback(
		(event: React.ChangeEvent<HTMLInputElement>) => {
			const file = event.target.files?.[0];
			if (!file) return;
			if (!file.name.endsWith('.json')) {
				toast.error('Please select a valid JSON file');
				return;
			}
			const reader = new FileReader();
			reader.onload = (e) => {
				try {
					const result = e.target?.result;
					if (typeof result !== 'string') throw new Error('Failed to read file');
					const loadedState: UndoableState = JSON.parse(result);
					if (
						!loadedState ||
						typeof loadedState !== 'object' ||
						!Array.isArray(loadedState.tracks) ||
						typeof loadedState.items !== 'object' ||
						typeof loadedState.assets !== 'object' ||
						typeof loadedState.fps !== 'number' ||
						typeof loadedState.compositionWidth !== 'number' ||
						typeof loadedState.compositionHeight !== 'number'
					) {
						throw new Error('Invalid state file format');
					}
					setState({
						update: (prevState: EditorState) => ({
							...prevState,
							undoableState: loadedState,
						}),
						commitToUndoStack: true,
					});
					toast.success('State loaded successfully');
				} catch (error) {
					toast.error(
						error instanceof Error
							? `Failed to load state: ${error.message}`
							: 'Failed to load state',
					);
				}
			};
			reader.onerror = () => toast.error('Failed to read file');
			reader.readAsText(file);
			event.target.value = '';
			setOpen(false);
		},
		[setState],
	);

	const saveDisabled = assetsUploading || assetsWithErrors;

	return (
		<div className="relative">
			<button
				ref={buttonRef}
				onClick={() => setOpen((v) => !v)}
				data-toolbar-btn
				className="editor-starter-focus-ring"
				data-active={open}
				title="File menu"
				aria-label="File menu"
				aria-expanded={open}
				aria-haspopup="menu"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					className="w-4 h-4"
				>
					<path d="M3.75 3A1.75 1.75 0 0 0 2 4.75v3.26a3.235 3.235 0 0 1 1.75-.51h12.5c.644 0 1.245.188 1.75.51V6.75A1.75 1.75 0 0 0 16.25 5h-4.836a.25.25 0 0 1-.177-.073L9.823 3.513A1.75 1.75 0 0 0 8.586 3H3.75ZM3.75 9A1.75 1.75 0 0 0 2 10.75v4.5c0 .966.784 1.75 1.75 1.75h12.5A1.75 1.75 0 0 0 18 15.25v-4.5A1.75 1.75 0 0 0 16.25 9H3.75Z" />
				</svg>
				<span>File</span>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					className="h-3.5 w-3.5 opacity-70"
				>
					<path
						fillRule="evenodd"
						d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
						clipRule="evenodd"
					/>
				</svg>
			</button>

			{open
				? createPortal(
						<div
							ref={menuRef}
							className="editor-dropdown-menu fixed z-[9999] w-52"
							style={{
								top: `${menuPosition.top}px`,
								left: `${menuPosition.left}px`,
							}}
							role="menu"
						>
							<button
								onClick={handleSave}
								disabled={saveDisabled}
								className="editor-dropdown-item disabled:cursor-not-allowed disabled:opacity-40"
								role="menuitem"
							>
								<span className="editor-dropdown-item-main">
									<SaveIcon />
									<span>Save</span>
								</span>
								<span className="editor-dropdown-shortcut">⌘S</span>
							</button>
							<button
								onClick={handleBackup}
								disabled={assetsUploading}
								className="editor-dropdown-item disabled:cursor-not-allowed disabled:opacity-40"
								role="menuitem"
							>
								<span className="editor-dropdown-item-main">
									<DownloadIcon />
									<span>Backup</span>
								</span>
							</button>
							<button
								onClick={handleRestore}
								disabled={assetsUploading}
								className="editor-dropdown-item disabled:cursor-not-allowed disabled:opacity-40"
								role="menuitem"
							>
								<span className="editor-dropdown-item-main">
									<UploadIcon />
									<span>Restore</span>
								</span>
							</button>
						</div>,
						document.body,
					)
				: null}

			<input
				ref={fileInputRef}
				type="file"
				accept=".json"
				style={{display: 'none'}}
				onChange={handleFileChange}
			/>
		</div>
	);
};
