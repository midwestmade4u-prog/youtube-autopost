# 📁 YouTube Channels Project — Folder Guide

---

## 🌱 BSG_Channel/
Everything for **Bible Story Garden**.

| Subfolder | What's inside |
|---|---|
| `Scripts/` | JSON episode scripts (01–10). These are the blueprints for each video. |
| `YouTube_Metadata/` | **BSG_YouTube_Metadata.xlsx** — titles, descriptions, tags & hashtags for YouTube uploads. Open this when uploading a video. |
| `Assets/` | Channel banner, profile picture, watermark image, and how-to guide. |

---

## 🧠 TMF_Channel/
Everything for **The Mind Files**.

| Subfolder | What's inside |
|---|---|
| `Scripts/` | JSON episode scripts for TMF videos. |
| `YouTube_Metadata/` | *(Add YouTube metadata here as episodes are ready)* |

---

## 🎬 App-Managed Folders *(don't rename or move these)*
These folders are used automatically by `video_app.py`. Moving them will break the app.

| Folder | Purpose |
|---|---|
| `BSG_Output/` | Finished BSG videos land here after generation. |
| `TMF_Output/` | Finished TMF videos land here after generation. |
| `bsg_voices/` | Custom voice files (optional). |
| `bsg_music/` | Background music files (optional — drop MP3s here to use your own). |
| `temp_work/` | Temporary files during video generation. Auto-cleaned. |

---

## ⚙️ App Files *(don't move)*

| File | Purpose |
|---|---|
| `video_app.py` | The main video creation app. Run with: `python3 video_app.py` |
| `config.json` | Stores your OpenAI and ElevenLabs API keys. |
| `start.sh` | Quick launch script (alternative to running Python directly). |

---

## 🗂️ _Archive/
Old files kept for reference. Safe to ignore.

---

## Workflow Summary

1. **Create a script** → Open the app → use "Generate Script" → save the JSON to `BSG_Channel/Scripts/`
2. **Make the video** → Paste JSON into the app → click Generate → video saves to `BSG_Output/`
3. **Upload to YouTube** → Open `BSG_Channel/YouTube_Metadata/BSG_YouTube_Metadata.xlsx` → copy title, description & tags → upload in YouTube Studio
