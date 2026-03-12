"""Generate small test audio fixture files."""
import wave
from pathlib import Path

from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, TBPM, TDRC

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURES.mkdir(exist_ok=True)


def make_wav(path: Path, duration_s: float = 0.5, sample_rate: int = 44100):
    """Create a tiny silent WAV file."""
    n_frames = int(sample_rate * duration_s)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)


def make_mp3_from_wav(wav_path: Path, mp3_path: Path):
    """Create a minimal valid MP3 by writing a single MPEG frame of silence.

    This is a bare-bones approach: write an ID3v2 header then a minimal
    MPEG audio frame so mutagen can parse it.
    """
    # Minimal MP3: an ID3v2 tag header + one valid MPEG audio frame
    # MPEG1 Layer3 44100Hz 128kbps stereo frame = 417 bytes
    # Frame header: 0xFF 0xFB 0x90 0x00
    frame_header = bytes([0xFF, 0xFB, 0x90, 0x00])
    frame_data = b"\x00" * 413  # padding to fill the frame (417 - 4 header bytes)

    with open(mp3_path, "wb") as f:
        f.write(frame_header + frame_data)


def add_id3_tags(mp3_path: Path, artist=None, title=None, album=None, genre=None, bpm=None, year=None):
    """Add ID3 tags to an MP3 file."""
    try:
        tags = ID3(mp3_path)
    except Exception:
        tags = ID3()

    if artist:
        tags.add(TPE1(encoding=3, text=[artist]))
    if title:
        tags.add(TIT2(encoding=3, text=[title]))
    if album:
        tags.add(TALB(encoding=3, text=[album]))
    if genre:
        tags.add(TCON(encoding=3, text=[genre]))
    if bpm:
        tags.add(TBPM(encoding=3, text=[str(bpm)]))
    if year:
        tags.add(TDRC(encoding=3, text=[str(year)]))

    tags.save(mp3_path)


if __name__ == "__main__":
    # 1. Well-tagged MP3
    p = FIXTURES / "Disclosure - Latch.mp3"
    make_mp3_from_wav(None, p)
    add_id3_tags(p, artist="Disclosure", title="Latch", album="Settle",
                 genre="House", bpm="122", year="2013")
    print(f"Created: {p.name}")

    # 2. Poorly-tagged MP3 (no artist/title)
    p = FIXTURES / "unknown_track.mp3"
    make_mp3_from_wav(None, p)
    print(f"Created: {p.name}")

    # 3. Messy filename
    p = FIXTURES / "DJ_Track_(1)_[www.example.com].mp3"
    make_mp3_from_wav(None, p)
    add_id3_tags(p, artist="SomeArtist", title="SomeTrack")
    print(f"Created: {p.name}")

    # 4. Near-duplicate (same artist+title, different file)
    p = FIXTURES / "Disclosure - Latch (HQ).mp3"
    make_mp3_from_wav(None, p)
    add_id3_tags(p, artist="Disclosure", title="Latch", album="Settle Deluxe",
                 genre="House", bpm="122", year="2013")
    print(f"Created: {p.name}")

    # 5. WAV file (no tags typically)
    p = FIXTURES / "Bonobo - Kerala.wav"
    make_wav(p, duration_s=0.3)
    print(f"Created: {p.name}")

    print("\nAll fixtures created!")
