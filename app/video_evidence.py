"""Video validation and descriptive metadata; original bytes stay private."""
import json
from pathlib import Path
VIDEO_EXTENSIONS={'.mp4','.m4v','.mov','.webm','.mkv','.avi'}
def is_video(record):
    try:return json.loads(record.get('metadata_json') or '{}').get('media_type')=='video'
    except (ValueError,TypeError):return False

def video_metadata(path):
    import cv2
    path=Path(path)
    if path.suffix.lower() not in VIDEO_EXTENSIONS:raise ValueError('Unsupported video extension.')
    capture=cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():raise ValueError('Cannot decode this video. Try an MP4 recording with a supported codec.')
        valid,frame=capture.read()
        if not valid or frame is None:raise ValueError('No readable video frame found.')
        fps=float(capture.get(cv2.CAP_PROP_FPS));frames=int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        return {'media_type':'video','size_bytes':path.stat().st_size,'width':int(frame.shape[1]),'height':int(frame.shape[0]),'fps_reported':fps if fps>0 else None,'frame_count_reported':frames if frames>0 else None,'duration_seconds_estimated':frames/fps if fps>0 and frames>0 else None,'metadata_note':'Container estimates only; full video, audio and identifying metadata are not inspected or scrubbed. No verified capture time.','creation_timestamp':None,'sensitive_fields':['Video metadata and visible/audio identifiers require manual review']}
    finally:capture.release()
