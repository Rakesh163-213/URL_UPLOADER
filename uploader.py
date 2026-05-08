import os
import tempfile
from PIL import Image, ImageOps
import ffmpeg
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


class VideoUploader:
    """Handles video uploads to Telegram with progress tracking and large file support"""

    def __init__(self, client, max_file_size):
        """
        Initialize the video uploader

        Args:
            client: Pyrogram Client instance
            max_file_size: Maximum file size in bytes
        """
        self.client = client
        self.max_file_size = max_file_size

    def get_cancel_keyboard(self):
        """Get inline keyboard with cancel button"""
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    def generate_thumbnail(self, video_path):
        """
        Generate a thumbnail from video without changing
        the original frame dimensions.

        Args:
            video_path: Path to the video file

        Returns:
            str: Path to generated thumbnail, or None if failed
        """

        thumbnail_path = None

        try:
            # Create temporary thumbnail file
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
                thumbnail_path = tmp_file.name

            # Extract frame at 1 second using ffmpeg
            (
                ffmpeg
                .input(video_path, ss="00:00:04")
                .output(
                    thumbnail_path,
                    vframes=1,
                    format="image2",
                    vcodec="mjpeg"
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            # Ensure image is valid RGB without resizing
            with Image.open(thumbnail_path) as img:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                    img.save(thumbnail_path, "JPEG", quality=85)

            return thumbnail_path

        except Exception as e:
            print(f"Error generating thumbnail: {e}")

            # Cleanup temp file
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)

            return None

    def get_video_duration(self, video_path):
        """
        Get video duration using ffmpeg

        Args:
            video_path: Path to the video file

        Returns:
            int: Duration in seconds, or None if failed
        """
        try:
            probe = ffmpeg.probe(video_path)
            duration = float(probe['format']['duration'])
            return int(duration)
        except Exception as e:
            print(f"Error getting video duration: {e}")
            return None

    

    async def upload_video(self, chat_id, file_path, tracker, caption=None):
        """
        Upload a video to Telegram with progress tracking

        Args:
            chat_id: Target chat ID
            file_path: Path to the video file
            tracker: ProgressTracker instance for progress updates
            caption: Optional caption for the video

        Returns:
            tuple: (success: bool, error: str or None)
        """
        try:
            file_size = os.path.getsize(file_path)

            # Check if file needs to be split
            if file_size > self.max_file_size:
                return await self._upload_large_file(chat_id, file_path, tracker, caption)
            else:
                return await self._upload_single_file(chat_id, file_path, tracker, caption)

        except Exception as e:
            return False, f"Upload error: {str(e)}"

    async def _upload_single_file(self, chat_id, file_path, tracker, caption):
        """Upload a single file within size limits"""
        thumbnail_path = None
        try:
            filename = os.path.basename(file_path)

            # Generate thumbnail
            thumbnail_path = self.generate_thumbnail(file_path)

            # Get video duration
            duration = self.get_video_duration(file_path)

            # Progress callback for upload
            def progress_callback(current, total):
                if tracker and not tracker.is_cancelled():
                    tracker.update_upload(current, total, filename)

            # Send the video with thumbnail and duration
            await self.client.send_video(
                chat_id=chat_id,
                video=file_path,
                caption=caption,
                video_cover=thumbnail_path,
                duration=duration,
                progress=progress_callback
            )

            return True, None

        except Exception as e:
            return False, f"Single file upload failed: {str(e)}"
        finally:
            # Cleanup thumbnail
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)

    async def _upload_large_file(self, chat_id, file_path, tracker, caption):
        """Split and upload large files"""
        try:
            file_size = os.path.getsize(file_path)
            part_size = self.max_file_size - (10 * 1024 * 1024)  # 10MB buffer
            num_parts = (file_size + part_size - 1) // part_size

            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)
            output_dir = os.path.dirname(file_path)

            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)

            # Split and upload each part
            for part_num in range(num_parts):
                if tracker and tracker.is_cancelled():
                    return False, "Upload cancelled by user"

                start_pos = part_num * part_size
                end_pos = min(start_pos + part_size, file_size)
                part_filename = f"{name}_part{part_num + 1}_of_{num_parts}{ext}"
                part_path = os.path.join(output_dir, part_filename)

                # Create part file
                try:
                    with open(file_path, 'rb') as src_file:
                        src_file.seek(start_pos)
                        part_data = src_file.read(end_pos - start_pos)

                    with open(part_path, 'wb') as part_file:
                        part_file.write(part_data)

                except Exception as e:
                    return False, f"Failed to create part file: {str(e)}"

                # Upload part
                part_caption = f"{caption} (Part {part_num + 1}/{num_parts})" if caption else f"Part {part_num + 1}/{num_parts}"
                part_thumbnail = None

                try:
                    # Generate thumbnail for this part
                    part_thumbnail = self.generate_thumbnail(part_path)

                    # Get duration for this part
                    part_duration = self.get_video_duration(part_path)

                    await self.client.send_video(
                        chat_id=chat_id,
                        video=part_path,
                        caption=part_caption,
                        video_cover=part_thumbnail,
                        duration=part_duration
                    )

                except Exception as e:
                    # Cleanup part file and thumbnail on upload failure
                    if os.path.exists(part_path):
                        os.remove(part_path)
                    if part_thumbnail and os.path.exists(part_thumbnail):
                        os.remove(part_thumbnail)
                    return False, f"Failed to upload part {part_num + 1}: {str(e)}"
                finally:
                    # Cleanup thumbnail
                    if part_thumbnail and os.path.exists(part_thumbnail):
                        os.remove(part_thumbnail)

                # Update progress
                if tracker:
                    progress = ((part_num + 1) / num_parts) * 100
                    tracker.update_upload(
                        end_pos,
                        file_size,
                        filename
                    )

                # Cleanup part file
                if os.path.exists(part_path):
                    os.remove(part_path)

            return True, None

        except Exception as e:
            return False, f"Large file upload failed: {str(e)}"
