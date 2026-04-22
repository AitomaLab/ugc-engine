'use client';

import React from 'react';
import {Wand2} from 'lucide-react';
import {clsx} from '../utils/clsx';

export const InspectorToggleButton: React.FC<{
	open: boolean;
	onToggle: () => void;
}> = ({open, onToggle}) => {
	return (
		<button
			data-toolbar-btn
			type="button"
			className={clsx(
				'editor-starter-focus-ring flex h-10 items-center justify-center gap-[6px] rounded px-3 text-white transition-colors',
				open ? 'bg-white/10' : 'hover:bg-white/10',
			)}
			title="Toggle Inspector"
			aria-label="Toggle Inspector"
			aria-pressed={open}
			onClick={onToggle}
		>
			<Wand2 className="h-4 w-4" />
			<span className="text-xs">Inspector</span>
		</button>
	);
};
