import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget
import os
import math
from utils import format_size, format_time, format_speed, sanitize_filename
from progress import ProgressTracker


class VideoDownloader:
    """Handle video downloads using yt-dlp"""

    def __init__(self, download_dir="downloads"):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)

    def format_bytes(self, size):
        """Converts bytes to MB/GB with 2 decimal places"""
        if size is None:
            return "Unknown size"
        power = 1024
        n = 0
        power_labels = ["Bytes", "KB", "MB", "GB", "TB"]
        while size >= power and n < len(power_labels) - 1:
            size /= power
            n += 1
        return f"{size:.2f} {power_labels[n]}"

    def get_video_info(self, url):
        """Extract video information without downloading"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'formats': self._get_available_formats(info),
                    'filesize': info.get('filesize', 0) or info.get('filesize_approx', 0)
                }
        except Exception as e:
            print(f"Error getting video info: {e}")
            return None

    def _get_available_formats(self, info):
        """Extract available video formats using the improved logic"""
        quality_map = {}
        formats = info.get("formats", [])

        for f in formats:
            height = f.get("height")
            ext = f.get("ext")
            acodec = f.get("acodec")
            vcodec = f.get("vcodec")
            filesize = f.get("filesize") or f.get("filesize_approx")

            # Only consider video formats (vcodec != "none")
            if height and vcodec != "none":
                # Save the highest quality per height
                if height not in quality_map or (filesize and filesize > quality_map[height].get("filesize", 0)):
                    quality_map[height] = {
                        "format_id": f["format_id"],
                        "ext": ext,
                        "filesize": filesize,
                        "height": height,
                        "quality": f"{height}p"
                    }

        # Convert to sorted list
        available_formats = sorted(quality_map.values(), key=lambda x: x["height"], reverse=True)
        return available_formats

    def get_quality_options(self, video_info, max_sizes):
        """Generate quality options based on available formats and size limits"""
        formats = video_info.get('formats', [])
        duration = video_info.get('duration', 0)
        options = []

        # Typical bitrates for different quality levels (in kbps)
        # Format: (height, min_bitrate, max_bitrate)
        quality_bitrates = {
            144: (100, 300),
            240: (300, 500),
            360: (500, 1000),
            480: (800, 1500),
            720: (1500, 3000),
            1080: (3000, 6000),
        }

        for quality, max_size_mb in max_sizes:
            if quality == 'best':
                # Best quality option - use the largest available format
                if formats:
                    best_format = formats[0]  # Already sorted by height (highest first)
                    actual_size = best_format.get('filesize') or best_format.get('filesize_approx')

                    # Calculate estimated size if actual size not available
                    if not actual_size and duration > 0:
                        height = best_format.get('height', 1080)
                        # Get bitrate range for this quality
                        bitrate_range = quality_bitrates.get(height, (3000, 6000))
                        avg_bitrate = (bitrate_range[0] + bitrate_range[1]) / 2
                        # Calculate size: (bitrate_kbps * duration_seconds) / 8 = KB
                        estimated_size = (avg_bitrate * duration) / 8 * 1024  # Convert to bytes
                        actual_size = int(estimated_size)

                    options.append({
                        'quality': 'Best Quality',
                        'max_size': max_size_mb * 1024 * 1024,
                        'format_id': best_format['format_id'],
                        'estimated_size': actual_size
                    })
            else:
                # Find format matching quality
                height = int(quality.replace('p', ''))
                matching = [f for f in formats if f['height'] == height]

                if matching:
                    fmt = matching[0]
                    actual_size = fmt.get('filesize') or fmt.get('filesize_approx')

                    # Calculate estimated size if actual size not available
                    if not actual_size and duration > 0:
                        # Get bitrate range for this quality
                        bitrate_range = quality_bitrates.get(height, (500, 1000))
                        avg_bitrate = (bitrate_range[0] + bitrate_range[1]) / 2
                        # Calculate size: (bitrate_kbps * duration_seconds) / 8 = KB
                        estimated_size = (avg_bitrate * duration) / 8 * 1024  # Convert to bytes
                        actual_size = int(estimated_size)

                    options.append({
                        'quality': f"{height}p",
                        'max_size': max_size_mb * 1024 * 1024,
                        'format_id': fmt['format_id'],
                        'estimated_size': actual_size
                    })

        return options

    def download_video(self, url, quality_option, progress_tracker, output_dir=None):
        """Download video with progress tracking"""
        if output_dir is None:
            output_dir = self.download_dir

        try:
            # Get video info first
            info = self.get_video_info(url)
            if not info:
                return None, "Failed to get video info"

            # Sanitize filename
            title = sanitize_filename(info['title'])
            output_template = os.path.join(output_dir, f"{title}.%(ext)s")

            # Configure yt-dlp options
            ydl_opts = {
                'format': quality_option.get('format_id', 'best'),
                'impersonate': ImpersonateTarget(client='chrome', version='136', os=None, os_version=None),
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [lambda d: self._progress_hook(d, progress_tracker)],
                'overwrite': True,
            }

            # Download
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Find downloaded file
            downloaded_file = os.path.join(output_dir, f"{title}.mp4")

            if os.path.exists(downloaded_file):
                return downloaded_file, None
            else:
                # Try to find any video file
                for file in os.listdir(output_dir):
                    if file.startswith(title) and file.endswith('.mp4'):
                        return os.path.join(output_dir, file), None

                return None, "Downloaded file not found"

        except Exception as e:
            if progress_tracker.is_cancelled():
                return None, "Download cancelled"
            return None, f"Download failed: {str(e)}"

    def _progress_hook(self, d, progress_tracker):
        """Progress hook for yt-dlp"""
        if progress_tracker.is_cancelled():
            raise Exception("Download cancelled by user")

        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            filename = d.get('filename', '')

            progress_tracker.update_download(downloaded, total, filename)

        elif d['status'] == 'finished':
            progress_tracker.update_download(
                d.get('total_bytes', 0),
                d.get('total_bytes', 0),
                d.get('filename', '')
            )
