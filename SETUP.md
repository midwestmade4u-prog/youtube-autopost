# Bible Story Garden — Video Maker Setup

## One-Time Setup (do this first)

### 1. Install Python packages
Open Terminal and run:
```
pip install edge-tts requests Pillow
```

### 2. Install FFmpeg
**Mac:**
```
brew install ffmpeg
```
**Windows:**
Download from https://ffmpeg.org/download.html and add to PATH.

---

## Running the App

In Terminal, navigate to this folder and run:
```
python3 bible_video_maker.py
```

The app will:
1. Generate AI images for each scene (Pollinations.ai — free)
2. Generate narration voiceover (Edge TTS — free)
3. Assemble everything into a finished MP4

Output video will be saved to the `bsg_output/` folder.

---

## Making a New Video

Open `bible_video_maker.py` in any text editor and find this section near the top:

```python
VIDEO_TITLE = "Noahs Ark"

SCENES = [
    {
        "narration": "The words that will be spoken aloud...",
        "image_prompt": "Description of what the image should look like..."
    },
    ...
]
```

- Change `VIDEO_TITLE` to your new video name
- Replace the `SCENES` list with your new script
- Save and run the app again

---

## Tips for Good Image Prompts

Always include:
- **Style**: "bright colorful animated children's bible storybook illustration"
- **Mood**: warm, cheerful, peaceful, hopeful
- **Subject**: what's happening in the scene
- **What NOT to include**: "no text, no words"

---

## Voice Options

To change the narrator voice, edit this line in the script:
```python
VOICE = "en-US-JennyNeural"
```

Other good options:
- `en-US-AriaNeural` — warm female
- `en-US-GuyNeural` — calm male
- `en-US-MichelleNeural` — friendly female
