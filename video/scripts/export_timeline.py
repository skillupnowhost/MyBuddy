#!/usr/bin/env python
"""Standalone video timeline export job runner (trim + concatenate).

Deliberately independent of the backend's `app` package — same reasoning as generate.py and
edit_video.py in this same directory: self-contained and independently runnable. Talks to
Postgres only to report its own status and to record the result video, via plain SQL.

Pure frame I/O via imageio — trims each source clip to its [trim_start_seconds,
trim_end_seconds) range and writes the frames in order into one output video. No ML model at
all, so (like REMOVE_BACKGROUND/REPLACE_ENVIRONMENT/COLOR_GRADE) this actually completes on
CPU-only hardware once video/.venv is provisioned.

Known limitation: the output uses the FIRST clip's fps for every clip. Splicing clips shot at
genuinely different frame rates without re-timing them is a real gap, not silently patched
over — see video/README.md.

Usage:
    python export_timeline.py --job-id <uuid> --user-id <uuid> \
        --clips-json '[{"storage_path": "...", "trim_start_seconds": 0, "trim_end_seconds": 5}]' \
        --storage-dir <path> --database-url <url>
"""
import argparse
import json
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, text


def update_job(engine, job_id: str, **fields) -> None:
    set_clause = ", ".join(
        f"{key} = CAST(:{key} AS uuid)" if key == "result_video_id" else f"{key} = :{key}" for key in fields
    )
    fields["job_id"] = job_id
    with engine.begin() as conn:
        conn.execute(
            text(f"UPDATE video_timeline_export_jobs SET {set_clause} WHERE id = CAST(:job_id AS uuid)"), fields
        )


def save_result_video(
    engine, user_id: str, storage_dir: str, video_path: str, width: int, height: int, duration_seconds: float
) -> str:
    """Same storage/insert convention as generate.py's save_generated_video."""
    user_dir = os.path.join(storage_dir, "videos", user_id)
    os.makedirs(user_dir, exist_ok=True)
    video_id = uuid.uuid4()
    final_path = os.path.join(user_dir, f"{uuid.uuid4().hex}.mp4")
    os.replace(video_path, final_path)
    size_bytes = os.path.getsize(final_path)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO videos (id, user_id, storage_path, content_type, width, height, "
                "duration_seconds, size_bytes, created_at) "
                "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :storage_path, :content_type, "
                ":width, :height, :duration_seconds, :size_bytes, now())"
            ),
            {
                "id": str(video_id),
                "user_id": user_id,
                "storage_path": final_path,
                "content_type": "video/mp4",
                "width": width,
                "height": height,
                "duration_seconds": duration_seconds,
                "size_bytes": size_bytes,
            },
        )
    return str(video_id)


def run_export(clips: list[dict]) -> tuple[str, int, int, float]:
    import tempfile

    import imageio

    if not clips:
        raise ValueError("clips must not be empty")

    fd, temp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)

    writer = None
    width = height = 0
    total_frames_written = 0
    fps = 24
    try:
        for i, clip in enumerate(clips):
            reader = imageio.get_reader(clip["storage_path"])
            try:
                meta = reader.get_meta_data()
                clip_fps = meta.get("fps", 24)
                if writer is None:
                    fps = clip_fps
                    writer = imageio.get_writer(temp_path, fps=fps)

                trim_start = clip.get("trim_start_seconds") or 0.0
                start_frame = round(trim_start * clip_fps)
                trim_end = clip.get("trim_end_seconds")
                end_frame = round(trim_end * clip_fps) if trim_end is not None else None

                for frame_index, frame in enumerate(reader):
                    if frame_index < start_frame:
                        continue
                    if end_frame is not None and frame_index >= end_frame:
                        break
                    width, height = frame.shape[1], frame.shape[0]
                    writer.append_data(frame)
                    total_frames_written += 1
            finally:
                reader.close()
    finally:
        if writer is not None:
            writer.close()

    if total_frames_written == 0:
        raise ValueError("export produced zero frames — check clip trim ranges")

    duration_seconds = total_frames_written / fps if fps else 0.0
    return temp_path, width, height, duration_seconds


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--clips-json", required=True)
    parser.add_argument("--storage-dir", required=True)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()

    clips = json.loads(args.clips_json)

    engine = create_engine(args.database_url)
    update_job(engine, args.job_id, status="RUNNING")

    try:
        temp_path, width, height, duration_seconds = run_export(clips)
        video_id = save_result_video(engine, args.user_id, args.storage_dir, temp_path, width, height, duration_seconds)
        update_job(
            engine,
            args.job_id,
            status="COMPLETED",
            result_video_id=video_id,
            completed_at=datetime.now(timezone.utc),
        )
        return 0
    except ImportError as exc:
        message = (
            f"Video export dependencies not installed: {exc}. "
            "Run 'pip install -r video/requirements.txt' before starting an export job."
        )
        update_job(engine, args.job_id, status="FAILED", error_message=message, completed_at=datetime.now(timezone.utc))
        print(message, file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - any export failure must be reported, not raised into the void
        message = f"{exc}\n{traceback.format_exc()}"[:4000]
        update_job(engine, args.job_id, status="FAILED", error_message=message, completed_at=datetime.now(timezone.utc))
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
