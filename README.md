# Voropitch

Voropitch is a Streamlit app for football match annotation: calibrate camera perspective using pitch lines, mark player positions, and export coordinates with optional Voronoi pitch-control visualization.


## Requirements

- Python 3.10 or newer (3.12 recommended)
- Dependencies listed in `requirements.txt`

## Run

```bash
streamlit run voropitch.py
```

## Workflow

1. **Upload** a match image (PNG/JPG) or MP4 video. For video, pick a frame with the slider.
2. **Draw four pitch lines** on the image: two horizontal, then two vertical. Match each line to the pitch diagram labels (UP, DP, RPA, RG by default).
3. **Mark players** with colored rectangles. The position is taken from the center of the rectangle base. Switch team color before drawing each side.
4. **Final output** shows camera and top-down views with optional Voronoi regions, player highlights, and a StatsBomb-format scatter plot. Download coordinates as CSV.
