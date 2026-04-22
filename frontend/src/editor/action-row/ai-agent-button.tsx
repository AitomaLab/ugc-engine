'use client';

import React from 'react';
import {Sparkles} from 'lucide-react';
import {clsx} from '../utils/clsx';

export const AiAgentButton: React.FC<{
	open: boolean;
	onToggle: () => void;
}> = ({open, onToggle}) => {
	return (
		<button
			data-toolbar-btn
			data-ai-agent
			type="button"
			className={clsx(
				'editor-starter-focus-ring flex h-[34px] items-center justify-center gap-1.5 rounded-[8px] border px-3 py-[6px] text-xs font-medium text-white transition-colors',
				'bg-[#1C1C1C] border-[#333333]',
				open
					? 'border-[#6D5FD5] hover:bg-[#252525]'
					: 'hover:bg-[#252525] hover:border-[#444444]',
			)}
			title={open ? 'Close Assistant' : 'Open Assistant'}
			aria-label={open ? 'Close Assistant' : 'Open Assistant'}
			aria-expanded={open}
			onClick={onToggle}
		>
			<Sparkles
				className={clsx('h-4 w-4', open ? 'text-[#C4B5FD]' : 'text-[#A78BFA]')}
			/>
			<span>AI</span>
		</button>
	);
};
