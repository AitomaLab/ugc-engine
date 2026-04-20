/**
 * Maps backend canonical `status_message` strings (English literals written
 * into video_jobs.status_message) to i18n translation keys so the UI can
 * display localized copy without changing the persisted value.
 *
 * If a message isn't in the map, fall back to rendering it raw — that
 * happens for uncommon one-off strings and keeps the UI from breaking.
 */

const JOB_STATUS_KEYS: Record<string, string> = {
    'Enhancing prompt...': 'creativeOs.jobStatus.enhancing_prompt',
    'Building animation prompt...': 'creativeOs.jobStatus.building_prompt',
    'Animating image (Kling 3.0)...': 'creativeOs.jobStatus.animating_kling',
    'Processing video...': 'creativeOs.jobStatus.processing_video',
    'KIE failed — retrying on WaveSpeed...': 'creativeOs.jobStatus.kie_retry',
    'Complete!': 'creativeOs.jobStatus.complete',
    'Generating Seedance video...': 'creativeOs.jobStatus.seedance_generating',
    'Uploading video...': 'creativeOs.jobStatus.uploading_video',
    'Preparing cinematic clip...': 'creativeOs.jobStatus.cinematic_preparing',
    'Building element references...': 'creativeOs.jobStatus.cinematic_building_refs',
    'References ready, building prompt...': 'creativeOs.jobStatus.cinematic_refs_ready',
    'Reference image ready, building prompt...': 'creativeOs.jobStatus.cinematic_ref_ready',
    'Building cinematic prompt...': 'creativeOs.jobStatus.cinematic_building_prompt',
    'Building cinematic multi-shot prompt...': 'creativeOs.jobStatus.cinematic_building_multi',
    'Splitting into cinematic shots...': 'creativeOs.jobStatus.cinematic_splitting',
    'Generating cinematic video with Kling 3.0...': 'creativeOs.jobStatus.cinematic_generating',
    'Generating cinematic video with Kling 3.0 (multi-shot)...': 'creativeOs.jobStatus.cinematic_generating_multi',
    'Preparing UGC clip...': 'creativeOs.jobStatus.ugc_preparing',
    'Analyzing product...': 'creativeOs.jobStatus.ugc_analyzing_product',
    'Generating script/dialogue...': 'creativeOs.jobStatus.ugc_script',
    'Animating reference image...': 'creativeOs.jobStatus.ugc_animating_ref',
    'Creating composite image...': 'creativeOs.jobStatus.ugc_composite',
    'Composite image ready, animating...': 'creativeOs.jobStatus.ugc_composite_ready',
    'Generating video...': 'creativeOs.jobStatus.ugc_generating',
    'Animating with Veo 3.1...': 'creativeOs.jobStatus.veo_animating',
};

/**
 * Resolve a backend status_message to a localized string via the `t`
 * function, or return the raw message if no mapping exists.
 */
export function localizeJobStatus(msg: string | null | undefined, t: (k: string) => string): string {
    if (!msg) return '';
    const key = JOB_STATUS_KEYS[msg];
    if (!key) return msg;
    const translated = t(key);
    return translated === key ? msg : translated;
}
