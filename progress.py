import time
from threading import Lock


class ProgressTracker:
    """Track progress for downloads and uploads with detailed information and animated progress bars"""

    # Animated progress bar characters
    ANIMATION_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    PROGRESS_BAR_CHARS = ['█', '▓', '▒', '░']

    def __init__(self, user_id, message_id, filename=None, quality=None):
        """
        Initialize progress tracker

        Args:
            user_id: User ID for the operation
            message_id: Message ID for progress updates
            filename: Optional filename being processed
            quality: Optional quality being downloaded
        """
        self.user_id = user_id
        self.message_id = message_id
        self.filename = filename or "Unknown"
        self.quality = quality or "Unknown"

        # Progress state
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.uploaded_bytes = 0
        self.upload_total = 0
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.last_downloaded = 0
        self.last_uploaded = 0
        self.cancelled = False
        self.operation = None  # 'download' or 'upload'
        self.lock = Lock()

        # Rate tracking
        self.download_speed = 0
        self.upload_speed = 0
        self.eta = 0

        # Animation state
        self.animation_frame = 0
        self.last_animation_update = time.time()

    def update_download(self, downloaded, total, filename=None):
        """Update download progress"""
        with self.lock:
            self.downloaded_bytes = downloaded
            self.total_bytes = total
            self.operation = 'download'
            if filename:
                self.filename = filename

            # Calculate speed and ETA more frequently
            current_time = time.time()
            time_elapsed = current_time - self.last_update_time

            # Update speed every 0.5 seconds for better responsiveness
            if time_elapsed >= 0.5:
                bytes_downloaded = downloaded - self.last_downloaded
                self.download_speed = bytes_downloaded / time_elapsed if time_elapsed > 0 else 0

                # Calculate ETA
                if self.download_speed > 0 and total > 0:
                    remaining = total - downloaded
                    self.eta = remaining / self.download_speed

                self.last_update_time = current_time
                self.last_downloaded = downloaded

    def update_upload(self, uploaded, total, filename=None):
        """Update upload progress"""
        with self.lock:
            self.uploaded_bytes = uploaded
            self.upload_total = total
            self.operation = 'upload'
            if filename:
                self.filename = filename

            # Calculate speed and ETA more frequently
            current_time = time.time()
            time_elapsed = current_time - self.last_update_time

            # Update speed every 0.5 seconds for better responsiveness
            if time_elapsed >= 0.5:
                bytes_uploaded = uploaded - self.last_uploaded
                self.upload_speed = bytes_uploaded / time_elapsed if time_elapsed > 0 else 0

                # Calculate ETA
                if self.upload_speed > 0 and total > 0:
                    remaining = total - uploaded
                    self.eta = remaining / self.upload_speed

                self.last_update_time = current_time
                self.last_uploaded = uploaded

    def update_progress(self, current, total, operation):
        """Legacy method for backward compatibility"""
        if operation == 'download':
            self.update_download(current, total)
        elif operation == 'upload':
            self.update_upload(current, total)

    def get_progress_text(self):
        """Get formatted progress text with all details"""
        with self.lock:
            if self.operation == 'download':
                return self._get_download_progress()
            elif self.operation == 'upload':
                return self._get_upload_progress()
            else:
                return "⏳ Starting..."

    def _get_download_progress(self):
        """Get download progress text with animated progress bar"""
        progress_percent = (self.downloaded_bytes / self.total_bytes * 100) if self.total_bytes > 0 else 0

        # Update animation frame
        current_time = time.time()
        if current_time - self.last_animation_update >= 0.1:  # Update every 100ms
            self.animation_frame = (self.animation_frame + 1) % len(self.ANIMATION_FRAMES)
            self.last_animation_update = current_time

        # Create animated progress bar
        bar_length = 20
        filled = int(bar_length * progress_percent / 100)

        # Use different characters for filled portion based on progress
        if progress_percent >= 100:
            bar = '█' * bar_length
        else:
            # Create gradient effect
            filled_chars = []
            for i in range(filled):
                if i == filled - 1 and progress_percent < 100:
                    filled_chars.append('▓')  # Partial fill at the edge
                else:
                    filled_chars.append('█')

            empty_chars = ['░'] * (bar_length - filled)
            bar = ''.join(filled_chars + empty_chars)

        # Add spinner animation
        spinner = self.ANIMATION_FRAMES[self.animation_frame]

        # Format sizes
        downloaded_mb = self.downloaded_bytes / (1024 * 1024)
        total_mb = self.total_bytes / (1024 * 1024) if self.total_bytes > 0 else 0

        # Format speed
        speed_mb = self.download_speed / (1024 * 1024)
        speed_text = f"{speed_mb:.2f} MB/s" if self.download_speed > 0 else "Calculating..."

        # Format ETA
        if self.eta > 0:
            eta_text = self._format_time(self.eta)
        else:
            eta_text = "Calculating..."

        # Build progress text
        lines = [
            f"📥 **Download Progress** {spinner}",
            f"",
            f"📁 **File:** {self.filename}",
            f"🎯 **Quality:** {self.quality}",
            f"",
            f"📊 **Progress:** {bar} {progress_percent:.1f}%",
            f"📦 **Size:** {downloaded_mb:.2f} MB / {total_mb:.2f} MB",
            f"⚡ **Speed:** {speed_text}",
            f"⏱️ **ETA:** {eta_text}",
        ]

        return "\n".join(lines)

    def _get_upload_progress(self):
        """Get upload progress text with animated progress bar"""
        progress_percent = (self.uploaded_bytes / self.upload_total * 100) if self.upload_total > 0 else 0

        # Update animation frame
        current_time = time.time()
        if current_time - self.last_animation_update >= 0.1:  # Update every 100ms
            self.animation_frame = (self.animation_frame + 1) % len(self.ANIMATION_FRAMES)
            self.last_animation_update = current_time

        # Create animated progress bar
        bar_length = 20
        filled = int(bar_length * progress_percent / 100)

        # Use different characters for filled portion based on progress
        if progress_percent >= 100:
            bar = '█' * bar_length
        else:
            # Create gradient effect
            filled_chars = []
            for i in range(filled):
                if i == filled - 1 and progress_percent < 100:
                    filled_chars.append('▓')  # Partial fill at the edge
                else:
                    filled_chars.append('█')

            empty_chars = ['░'] * (bar_length - filled)
            bar = ''.join(filled_chars + empty_chars)

        # Add spinner animation
        spinner = self.ANIMATION_FRAMES[self.animation_frame]

        # Format sizes
        uploaded_mb = self.uploaded_bytes / (1024 * 1024)
        total_mb = self.upload_total / (1024 * 1024) if self.upload_total > 0 else 0

        # Format speed
        speed_mb = self.upload_speed / (1024 * 1024)
        speed_text = f"{speed_mb:.2f} MB/s" if self.upload_speed > 0 else "Calculating..."

        # Format ETA
        if self.eta > 0:
            eta_text = self._format_time(self.eta)
        else:
            eta_text = "Calculating..."

        # Build progress text
        lines = [
            f"📤 **Upload Progress** {spinner}",
            f"",
            f"📁 **File:** {self.filename}",
            f"",
            f"📊 **Progress:** {bar} {progress_percent:.1f}%",
            f"📦 **Size:** {uploaded_mb:.2f} MB / {total_mb:.2f} MB",
            f"⚡ **Speed:** {speed_text}",
            f"⏱️ **ETA:** {eta_text}",
        ]

        return "\n".join(lines)

    def _format_time(self, seconds):
        """Format seconds to HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def should_update(self):
        """Check if progress should be updated (always true for active operations to show animation)"""
        current_time = time.time()
        time_since_update = current_time - self.last_update_time
        # Always update if there's an active operation to show animation
        return self.operation is not None and time_since_update >= 0.5

    def get_download_progress(self):
        """Get download progress as percentage (legacy method)"""
        with self.lock:
            if self.total_bytes > 0:
                return (self.downloaded_bytes / self.total_bytes) * 100
            return 0

    def get_upload_progress(self):
        """Get upload progress as percentage (legacy method)"""
        with self.lock:
            if self.upload_total > 0:
                return (self.uploaded_bytes / self.upload_total) * 100
            return 0

    def get_speed(self):
        """Get current download/upload speed in bytes/second (legacy method)"""
        with self.lock:
            elapsed = self.last_update_time - self.start_time
            if elapsed > 0:
                if self.operation == 'download':
                    return self.downloaded_bytes / elapsed
                elif self.operation == 'upload':
                    return self.uploaded_bytes / elapsed
            return 0

    def is_cancelled(self):
        """Check if operation was cancelled"""
        with self.lock:
            return self.cancelled

    def cancel(self):
        """Cancel the operation"""
        with self.lock:
            self.cancelled = True

    def reset(self):
        """Reset tracker for new operation"""
        with self.lock:
            self.downloaded_bytes = 0
            self.total_bytes = 0
            self.uploaded_bytes = 0
            self.upload_total = 0
            self.start_time = time.time()
            self.last_update_time = time.time()
            self.last_downloaded = 0
            self.last_uploaded = 0
            self.download_speed = 0
            self.upload_speed = 0
            self.eta = 0
            self.cancelled = False
            self.animation_frame = 0
            self.last_animation_update = time.time()


class ProgressManager:
    """Manage multiple progress trackers"""

    def __init__(self):
        self.trackers = {}
        self.lock = Lock()

    def create_tracker(self, user_id, message_id, filename=None, quality=None):
        """Create a new progress tracker"""
        key = (user_id, message_id)
        with self.lock:
            tracker = ProgressTracker(user_id, message_id, filename, quality)
            self.trackers[key] = tracker
            return tracker

    def get_tracker(self, user_id, message_id):
        """Get existing tracker"""
        key = (user_id, message_id)
        with self.lock:
            return self.trackers.get(key)

    def remove_tracker(self, user_id, message_id):
        """Remove tracker"""
        key = (user_id, message_id)
        with self.lock:
            if key in self.trackers:
                del self.trackers[key]

    def get_all_trackers(self):
        """Get all active trackers"""
        with self.lock:
            return list(self.trackers.values())