import tempfile
import os
import re
import gdown


class GDriveService:
    """
    Handles downloading files from Google Drive.
    """

    @staticmethod
    def _extract_file_id(url: str) -> str:
        """
        Extracts the Google Drive file ID from a standard sharing link.
        """
        # Matches the ID between /d/ and /view
        match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
        if match:
            return match.group(1)

        # Matches the ID in a uc?id= format
        match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
        if match:
            return match.group(1)

        raise ValueError("Could not extract Google Drive File ID from the provided link.")

    @staticmethod
    def download_file(file_url: str) -> str:
        """
        Downloads a file from a public Google Drive URL to a temporary file.

        Args:
            file_url (str): The public Google Drive URL of the file.

        Returns:
            str: The path to the temporary file.
        """
        # Extract the actual file ID from the sharing link
        try:
            file_id = GDriveService._extract_file_id(file_url)
        except ValueError as e:
            raise ValueError(f"Invalid Google Drive URL: {e}")

        # Construct the direct download URL that gdown expects
        direct_url = f"https://drive.google.com/uc?id={file_id}"

        # Create a temporary file safely
        fd, temp_path = tempfile.mkstemp(suffix=".mp4")

        # Close the file descriptor immediately so gdown can open and write to it
        os.close(fd)

        try:
            # Use gdown to handle the download, bypassing the virus scan warning
            output_path = gdown.download(direct_url, temp_path, quiet=False)

            # Verify the file was actually downloaded and isn't empty
            if output_path is None or os.path.getsize(temp_path) == 0:
                raise RuntimeError("Download failed or file is empty.")

            return temp_path

        except Exception as e:
            # Clean up if download fails
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise RuntimeError(f"Failed to download video from Google Drive: {e}")

    @staticmethod
    def cleanup_file(file_path: str):
        """
        Removes the temporary file.

        Args:
            file_path (str): The path to the file to remove.
        """
        if os.path.exists(file_path):
            os.remove(file_path)