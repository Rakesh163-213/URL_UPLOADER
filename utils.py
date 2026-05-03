import os
import subprocess
from PIL import Image
import ffmpeg


def generate_thumbnail(video_path, output_path="thumbnail.jpg"):
    """Generate a 320x320 thumbnail from video"""
    try:
        # Get video duration
        probe = ffmpeg.probe(video_path)
        duration = float(probe['format']['duration'])

        # Calculate timestamp (10% or 30 seconds, whichever comes first)
        timestamp = min(duration * 0.1, 30)

        # Extract frame using ffmpeg
        (
            ffmpeg
            .input(video_path, ss=timestamp)
            .output(output_path, vframes=1, format='image2', vcodec='mjpeg')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

        # Resize to 320x320 using Pillow
        img = Image.open(output_path)
        img = img.resize((320, 320), Image.Resampling.LANCZOS)
        img.save(output_path, 'JPEG', quality=85)

        return output_path
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return None


def get_video_duration(video_path):
    """Get video duration in seconds"""
    try:
        probe = ffmpeg.probe(video_path)
        return float(probe['format']['duration'])
    except Exception as e:
        print(f"Error getting duration: {e}")
        return 0


def split_video(input_path, max_size=1.9 * 1024 * 1024 * 1024):
    """Split video into parts if larger than max_size"""
    file_size = os.path.getsize(input_path)

    if file_size <= max_size:
        return [input_path]

    parts = []
    part_num = 1
    current_size = 0
    duration = get_video_duration(input_path)

    # Calculate approximate duration per part
    part_duration = (max_size / file_size) * duration

    output_dir = os.path.dirname(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]

    while current_size < duration:
        start_time = current_size
        end_time = min(current_size + part_duration, duration)

        output_path = os.path.join(output_dir, f"{base_name}_part{part_num}.mp4")

        try:
            (
                ffmpeg
                .input(input_path, ss=start_time, t=end_time - start_time)
                .output(output_path, c='copy')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            parts.append(output_path)
            part_num += 1
            current_size = end_time

        except Exception as e:
            print(f"Error splitting video: {e}")
            break

    return parts


def format_size(bytes_size):
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def format_time(seconds):
    """Format seconds to HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_speed(bytes_per_second):
    """Format bytes per second to human readable speed"""
    return format_size(bytes_per_second) + "/s"


def sanitize_filename(filename):
    """Sanitize filename for safe file system usage"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename


def cleanup_files(file_paths):
    """Delete files from filesystem"""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted: {file_path}")
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")
