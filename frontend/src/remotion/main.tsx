import {FontInfo} from '@remotion/google-fonts';
import React, {useMemo} from 'react';
import {EditorStarterAsset} from '../editor/assets/assets';
import {MainComposition} from '../editor/canvas/composition';
import {
	ActiveCanvasSnap,
	ActiveCanvasSnapContext,
	AllItemsContext,
	AssetsContext,
	AssetStatusContext,
	TracksContext,
} from '../editor/context-provider';
import {EditorStarterItem} from '../editor/items/item-type';
import {TrackType} from '../editor/state/types';
import {FontInfoContext} from '../editor/utils/text/font-info';

export type CompositionWithContextsProps = {
	tracks: TrackType[];
	items: Record<string, EditorStarterItem>;
	assets: Record<string, EditorStarterAsset>;
	compositionWidth: number;
	compositionHeight: number;
	fontInfos: Record<string, FontInfo>;
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
