import {EditorStarterAsset} from '../assets/assets';
import {EditorStarterItem} from '../items/item-type';
import {TrackType} from '../state/types';
import {VideoCodec} from '../utils/export-file-name';

export type RenderVideoPayload = {
	compositionHeight: number;
	compositionWidth: number;
	tracks: TrackType[];
	items: Record<string, EditorStarterItem>;
	assets: Record<string, EditorStarterAsset>;
	codec: VideoCodec;
};

export type RenderVideoResponse =
	| {
			type: 'success';
			bucketName: string;
			renderId: string;
	  }
	| {
			type: 'error';
			error: string;
	  };

export type GetProgressResponse =
	| {
			type: 'done';
			outputFile: string;
			outputSizeInBytes: number;
			outputName: string;
	  }
	| {
			type: 'in-progress';
			overallProgress: number;
	  }
	| {
			type: 'error';
			error: string;
	  };

export type GetProgressPayload = {
	bucketName: string;
	renderId: string;
};
