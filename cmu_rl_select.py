import html
import os
import re
import urllib.request

import numpy as np


ROOT = r"D:\paper download materials\cmu\CMU\CMU"

TRIAL_RE = re.compile(
    r'<TR[^>]*><TD></TD><TD>(\d+)</TD><TD>(.*?)</TD>.*?<TD>(\d+)</TD><TD><A HREF="badtrial',
    re.IGNORECASE | re.DOTALL,
)

INCLUDE_RE = re.compile(
    r"\b(stand|walk|turn|run|jump|hop|kick|punch|dance|stretch|bend|squat|march|shuffle|crawl)\b",
    re.IGNORECASE,
)

EXCLUDE_RE = re.compile(
    r"(stairs|stair|chair|ladder|playground|basketball|football|ball|box|swing|throw|catch|"
    r"dribble|carry|pick up|wash|mop|wood|ledge|climb|horse|cart|sword|stick|terrain|"
    r"uneven|pushing|pulling|subject|two subjects|couple|partner|object)",
    re.IGNORECASE,
)


def scan_frames():
    frames = {}
    for dirpath, _, filenames in os.walk(ROOT):
        subject = os.path.basename(dirpath)
        for filename in filenames:
            match = re.match(r"(.+?)_(\d+)_poses\.npz$", filename)
            if not match:
                continue
            motion = int(match.group(2))
            path = os.path.join(dirpath, filename)
            try:
                data = np.load(path)
                frame_count = int(data["poses"].shape[0])
                framerate = float(data["mocap_framerate"])
            except Exception:
                continue
            frames[(subject, motion)] = (frame_count, framerate, path)
    return frames


def fetch_descriptions(subjects):
    descriptions = {}
    for subject in subjects:
        if not re.fullmatch(r"\d+", subject):
            continue
        url = f"http://mocap.cs.cmu.edu/search.php?subjectnumber={int(subject)}"
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                page = response.read().decode("latin1", "ignore")
        except Exception:
            continue
        for motion, raw_description, _ in TRIAL_RE.findall(page):
            description = html.unescape(re.sub("<.*?>", "", raw_description)).strip()
            descriptions[(subject, int(motion))] = description
    return descriptions


def main():
    frames = scan_frames()
    subjects = sorted({subject for subject, _ in frames if re.fullmatch(r"\d+", subject)}, key=int)
    descriptions = fetch_descriptions(subjects)

    rows = []
    for key, (frame_count, framerate, path) in frames.items():
        if key not in descriptions or framerate <= 0:
            continue
        seconds = frame_count / framerate
        description = descriptions[key]
        rows.append(
            {
                "id": f"{key[0]}_{key[1]:02d}",
                "frames": frame_count,
                "seconds": seconds,
                "framerate": framerate,
                "description": description,
                "path": path,
            }
        )

    candidates = [
        row
        for row in rows
        if 8.5 <= row["seconds"] <= 11.8
        and INCLUDE_RE.search(row["description"])
        and not EXCLUDE_RE.search(row["description"])
    ]
    candidates.sort(key=lambda row: (abs(row["seconds"] - 10.0), row["id"]))

    print(f"candidate_count\t{len(candidates)}")
    for row in candidates[:180]:
        print(
            f'{row["id"]}\t{row["frames"]}\t{row["seconds"]:.2f}s\t'
            f'{row["framerate"]:g}fps\t{row["description"]}\t{row["path"]}'
        )


if __name__ == "__main__":
    main()
