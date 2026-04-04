import React from 'react';
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from '../select';

export type CodecOption = 'h264' | 'vp8';

interface CodecSelectorProps {
	value: CodecOption;
	onValueChange: (value: CodecOption) => void;
}

export const CodecSelector: React.FC<CodecSelectorProps> = ({
	value,
	onValueChange,
}) => {
	return (
		<Select value={value} onValueChange={onValueChange}>
			<SelectTrigger className="w-full">
				<SelectValue placeholder="Select codec" />
			</SelectTrigger>
			<SelectContent className="w-full">
				<SelectItem value="h264">
					<span className="text-xs text-neutral-300">MP4 (H.264)</span>
				</SelectItem>
				<SelectItem value="vp8">
					<span className="text-xs text-neutral-300">WebM (VP8)</span>
				</SelectItem>
			</SelectContent>
		</Select>
	);
};
