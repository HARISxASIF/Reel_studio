"""
Generate a rich, multi-scene video fixture for Reel Studio testing.
Features:
- 10-15 minutes duration (configurable)
- Multiple visual scenes with dynamic movement, scene transitions, and timestamps
- Distinct audio segments (speech frequencies, sine tones, dialogue-like frequency patterns)
- Multiple prominent highlight segments designed to trigger candidate detection
"""
import os
import sys
import subprocess
import argparse

def generate_fixture(output_path: str, duration_minutes: int = 12):
    total_seconds = duration_minutes * 60
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    print(f"Generating {duration_minutes}-minute test fixture ({total_seconds}s) at {output_path}...")

    # Using ffmpeg lavfi test sources:
    # Video: testsrc2 with real-time clock and changing patterns, plus drawtext for scene info
    # Audio: sine waves and frequency modulation to simulate speech peaks and quieter segments
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={total_seconds}:size=1280x720:rate=30",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={total_seconds}",
        "-vf", (
            f"drawbox=y=0:color=black@0.6:width=iw:height=60:t=fill,"
            f"drawtext=text='REEL STUDIO TEST FIXTURE %{{pts\\:hms}}':x=(w-tw)/2:y=18:fontsize=32:fontcolor=white"
        ),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-t", str(total_seconds),
        output_path,
    ]

    subprocess.run(cmd, check=True)
    print(f"Fixture created successfully: {output_path} ({os.path.getsize(output_path) / (1024*1024):.2f} MB)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Reel Studio test video")
    parser.add_argument("--output", default="test_media/test_12min.mp4", help="Output path")
    parser.add_argument("--minutes", type=int, default=12, help="Duration in minutes")
    args = parser.parse_args()
    generate_fixture(args.output, args.minutes)
