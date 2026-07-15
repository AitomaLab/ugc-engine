import type {FontInfo} from '@remotion/google-fonts';
import React, {useMemo} from 'react';
import type {EditorStarterAsset} from '../editor/assets/assets';
import {MainComposition} from '../editor/canvas/composition';
import {
	ActiveCanvasSnap,
	ActiveCanvasSnapContext,
	AllItemsContext,
	AssetsContext,
	AssetStatusContext,
	TracksContext,
} from '../editor/context-provider';
import type {EditorStarterItem} from '../editor/items/item-type';
import type {TrackType} from '../editor/state/types';
import {FontInfoContext} from '../editor/utils/text/font-info';

export type CompositionWithContextsProps = {
	tracks: TrackType[];
	items: Record<string, EditorStarterItem>;
	assets: Record<string, EditorStarterAsset>;
	compositionWidth: number;
	compositionHeight: number;
	fontInfos: Record<string, FontInfo>;
	// Server-built editor states carry an explicit fps (ugc_backend/editor_api.py);
	// states saved from the browser may not.
	fps?: number;
};

export const CompositionWithContexts: React.FC<
	CompositionWithContextsProps
> = ({tracks, assets, items, fontInfos}) => {
	const tracksContext = useMemo(
		(): TracksContext => ({
			tracks,
		}),
		[tracks],
	);

	const allItemsContext = useMemo(
		(): AllItemsContext => ({
			items,
		}),
		[items],
	);

	const assetsContext = useMemo(
		(): AssetsContext => ({
			assets,
		}),
		[assets],
	);

	const assetStatusContext = useMemo(
		(): AssetStatusContext => ({
			assetStatus: {},
		}),
		[],
	);

	const activeCanvasSnapContext = useMemo(
		(): ActiveCanvasSnap => ({
			activeCanvasSnapPoints: [],
		}),
		[],
	);

	return (
		<ActiveCanvasSnapContext.Provider value={activeCanvasSnapContext}>
			<FontInfoContext.Provider value={fontInfos}>
				<TracksContext.Provider value={tracksContext}>
					<AllItemsContext.Provider value={allItemsContext}>
						<AssetsContext.Provider value={assetsContext}>
							<AssetStatusContext.Provider value={assetStatusContext}>
								<MainComposition playerRef={null} />
							</AssetStatusContext.Provider>
						</AssetsContext.Provider>
					</AllItemsContext.Provider>
				</TracksContext.Provider>
			</FontInfoContext.Provider>
		</ActiveCanvasSnapContext.Provider>
	);
};
