import json
import logging
import re
import subprocess


def extract_start_location(file_path: str) -> tuple[float, float] | None:
    """
    Uses ffprobe to extract ISO 6709 GPS coordinates from video metadata.
    Returns (latitude, longitude) or None if not found.
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        # Look for the 'location' tag in the format metadata
        tags = data.get("format", {}).get("tags", {})

        # Keys are often lowercase, but sometimes vary
        # We check both standard 'location' and Apple/DJI specific tags
        location_str = tags.get("location") or tags.get("location-eng") or tags.get("xyz")

        if location_str:
            # Matches strings like +27.5916+086.5640/ or +35.2428-120.6625/
            match = re.search(r'([+-]\d+\.\d+)([+-]\d+\.\d+)', location_str)
            if match:
                lat = float(match.group(1))
                lon = float(match.group(2))
                return lat, lon

    except Exception as e:
        logging.info(f"Could not extract GPS data: {e}")

    return None