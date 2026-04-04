import React, {useMemo, useRef} from 'react';
import {EditorStarterItem} from '../../items/item-type';
import {clsx} from '../../utils/clsx';
import {useItemDrag} from '../utils/drag/use-timeline-item-drag';

export const TIMELINE_ITEM_BORDER_WIDTH = 1;

export function TimelineItemContainer({
	children,
	isSelected,
	item,
}: {
	children: React.ReactNode;
	isSelected: boolean;
	item: EditorStarterItem;
}) {
	const timelineItemRef = useRef<HTMLDivElement>(null);

	const {onPointerDown, onClick} = useItemDrag({
		draggedItem: item,
	});

	const style = useMemo(() => {
		return {
			borderWidth: TIMELINE_ITEM_BORDER_WIDTH,
		};
	}, []);

	return (
		<div
			ref={timelineItemRef}
			onPointerDown={onPointerDown}
			onClick={onClick}
			className={clsx(
				'absolute box-border h-full w-full cursor-pointer overflow-hidden rounded-sm border border-black select-none',
				isSelected && 'border-editor-starter-accent',
			)}
			style={style}
		>
			{children}
		</div>
	);
}
