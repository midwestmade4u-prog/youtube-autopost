#!/usr/bin/env python3
"""
ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
ÃÂ¢ÃÂÃÂ         Auto-Post ÃÂ¢ÃÂÃÂ MidwestMade4U Video Publisher           ÃÂ¢ÃÂÃÂ
ÃÂ¢ÃÂÃÂ         Bible Story Garden + The Mind Files                  ÃÂ¢ÃÂÃÂ
ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

Fully automated video creation and YouTube upload.
Picks a fresh topic, generates a script, creates the video,
and posts it ÃÂ¢ÃÂÃÂ zero input required.

Usage:
    python3 auto_post.py --channel bsg
    python3 auto_post.py --channel tmf
    python3 auto_post.py --trigger-file /path/to/trigger.json

Runs with consistent settings:
  BSG:  Rachel voice (ElevenLabs), 8 scenes, warm ambient music
  TMF:  Adam voice (ElevenLabs), 8 scenes, atmospheric ambient music
"""

import argparse
import json
import os
import random
import re as _re_imports
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Paths ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
BASE_DIR = Path(__file__).parent
LOG_FILE     = BASE_DIR / "auto_post_log.json"
# Per-channel dedup files ÃÂ¢ÃÂÃÂ each workflow only commits its own file, preventing
# merge conflicts when all three channels run concurrently in GH Actions.
BSG_LOG_FILE = BASE_DIR / "bsg_post_log.json"
TMF_LOG_FILE = BASE_DIR / "tmf_post_log.json"

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Voice Settings ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
CHANNEL_VOICES = {
    "bsg": "en-US-JennyNeural",   # Jenny  ÃÂ¢ÃÂÃÂ warm female (edge-tts; ElevenLabs Rachel retired May 2026)
    "tmf": "en-US-GuyNeural",     # Guy    ÃÂ¢ÃÂÃÂ deep male (edge-tts; ElevenLabs Adam 401 issues May 2026)
}

CHANNEL_LABELS = {
    "bsg": "Bible Story Garden",
    "tmf": "The Mind Files",
}

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Topic Banks ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
# These cycle in random order ÃÂ¢ÃÂÃÂ once all are used, the cycle resets.
# Add more topics here any time to expand the content library.

BSG_TOPICS = [
    "Noah's Ark ÃÂ¢ÃÂÃÂ Why God Chose ONE Man to Save All Life on Earth",
    "David vs Goliath ÃÂ¢ÃÂÃÂ How a Boy Defeated an IMPOSSIBLE Giant",
    "Moses Parted the Red Sea ÃÂ¢ÃÂÃÂ The Most INCREDIBLE Miracle Ever",
    "The Birth of Jesus ÃÂ¢ÃÂÃÂ The Night That Changed EVERYTHING",
    "Daniel in the Lion's Den ÃÂ¢ÃÂÃÂ Thrown to Certain Death, He Survived the IMPOSSIBLE",
    "Jonah and the Whale ÃÂ¢ÃÂÃÂ Swallowed Alive, But God Had Other Plans",
    "Joseph's Coat of Many Colors ÃÂ¢ÃÂÃÂ From SLAVE to POWERFUL Ruler",
    "The Good Samaritan ÃÂ¢ÃÂÃÂ A Stranger's Act of Compassion That Changed EVERYTHING",
    "Zacchaeus ÃÂ¢ÃÂÃÂ The HATED Man Jesus Chose to Save",
    "The Prodigal Son ÃÂ¢ÃÂÃÂ A Father's Love THAT Never Fails",
    "Jesus Feeds 5000 ÃÂ¢ÃÂÃÂ How One Miracle Fed an IMPOSSIBLE Crowd",
    "Moses and the Ten Commandments ÃÂ¢ÃÂÃÂ The MOMENT God Gave His Law",
    "Ruth and Naomi ÃÂ¢ÃÂÃÂ From DESPAIR to HOPE Against All Odds",
    "Esther Saves Her People ÃÂ¢ÃÂÃÂ A Queen's Brave Act Prevented GENOCIDE",
    "The Creation Story ÃÂ¢ÃÂÃÂ How God Made EVERYTHING in 6 Days",
    "Adam and Eve ÃÂ¢ÃÂÃÂ The FIRST Humans and Their Forbidden Choice",
    "Abraham and Isaac ÃÂ¢ÃÂÃÂ A Father's ULTIMATE Test of Faith",
    "The Tower of Babel ÃÂ¢ÃÂÃÂ Why God CONFUSED All Human Languages",
    "Elijah on Mount Carmel ÃÂ¢ÃÂÃÂ Fire From Heaven DEFEATS 450 Prophets",
    "Saul's Conversion ÃÂ¢ÃÂÃÂ From PERSECUTOR to Apostle in ONE MOMENT",
    "Jesus Walks on Water ÃÂ¢ÃÂÃÂ He Did What SEEMED IMPOSSIBLE",
    "The Easter Story ÃÂ¢ÃÂÃÂ Jesus ROSE FROM THE DEAD (Here's What Happened)",
    "The Christmas Story ÃÂ¢ÃÂÃÂ The Night Jesus Was BORN (What Really Happened)",
    "Solomon Asks for Wisdom ÃÂ¢ÃÂÃÂ God Granted Him EVERYTHING Else Too",
    "Gideon's 300 Warriors ÃÂ¢ÃÂÃÂ How a TINY Army Defeated 135,000 Enemies",
    "Samson's Incredible Strength ÃÂ¢ÃÂÃÂ Betrayed, Blinded, Yet He Destroyed His Enemies",
    "Joshua and the Walls of Jericho ÃÂ¢ÃÂÃÂ They FELL by Simply Walking Around Them",
    "Lazarus Raised From the Dead ÃÂ¢ÃÂÃÂ Dead 4 Days, Then Jesus Said ONE Thing",
    "Jesus Calms the Storm ÃÂ¢ÃÂÃÂ His Disciples Watched Him DO the IMPOSSIBLE",
    "Peter Walks on Water ÃÂ¢ÃÂÃÂ Until He Made ONE Mistake",
    "The Lost Sheep ÃÂ¢ÃÂÃÂ Jesus Leaves 99 to Find ONE",
    "Shadrach, Meshach, Abednego ÃÂ¢ÃÂÃÂ Thrown Into a Fiery Furnace, They SURVIVED",
    "Nehemiah Rebuilds Jerusalem ÃÂ¢ÃÂÃÂ One Man's IMPOSSIBLE Mission to Rebuild the Walls",
    "Samuel Hears God's Voice ÃÂ¢ÃÂÃÂ A Boy Chosen to Become a POWERFUL Prophet",
    "Deborah the Judge ÃÂ¢ÃÂÃÂ A Woman Who DEFEATED an Entire Army",
    # Removed May 2026 (analytics confirm doctrine/teaching underperforms):
    # "Psalm 23" ÃÂ¢ÃÂÃÂ no story arc, pure doctrine
    # "The Beatitudes" ÃÂ¢ÃÂÃÂ moral teaching list, no action/conflict
    # "Mary and Martha" ÃÂ¢ÃÂÃÂ low-stakes teaching moment
    # "David and Jonathan" ÃÂ¢ÃÂÃÂ friendship theme, not high-stakes action
    # "Elisha and the Widow's Oil" ÃÂ¢ÃÂÃÂ quiet miracle, limited visual spectacle
    # Added May 2026 ÃÂ¢ÃÂÃÂ narrative-heavy, high-stakes, clear visual payoff:
    "The Ten Plagues of Egypt ÃÂ¢ÃÂÃÂ God's Most DEVASTATING Display of Power",
    "Jacob Wrestles an Angel ÃÂ¢ÃÂÃÂ The Night a Man Fought God and SURVIVED",
    "Paul and Silas in Prison ÃÂ¢ÃÂÃÂ Chains FELL OFF at Midnight",
    "Balaam's Donkey ÃÂ¢ÃÂÃÂ The Day a Donkey Spoke to SAVE a Prophet's Life",
    "The Transfiguration ÃÂ¢ÃÂÃÂ Jesus Revealed His FULL GLORY on a Mountain",
    "Ananias and Sapphira ÃÂ¢ÃÂÃÂ The Couple Who Lied to God and DIED Instantly",
    "Stephen's Stoning ÃÂ¢ÃÂÃÂ The First Christian Martyr's FINAL Words",
    "The Feeding of 5000 ÃÂ¢ÃÂÃÂ 5 Loaves, 2 Fish, 5,000 People FED",
    "Elijah Fed by Ravens ÃÂ¢ÃÂÃÂ God Provided in the Most IMPOSSIBLE Way",
    "Jesus Clears the Temple ÃÂ¢ÃÂÃÂ He Was FURIOUS and Flipped EVERYTHING",
    "Joshua Stops the Sun ÃÂ¢ÃÂÃÂ God Made Time STAND STILL for One Battle",
    # ---- Bank refill, Aug 23 2026 ----------------------------------
    # The bank hit ZERO eligible topics on Aug 2 2026 and stayed there.
    # Every run since drew from the full bank with dedup bypassed, which
    # is how 'The Birth of Jesus' published 3x in five days. None of the
    # stories below resolve to an already-published slug.
    "Cain and Abel ÃÂ¢ÃÂÃÂ The First Murder and the Question God Asked",
    "Jacob's Ladder ÃÂ¢ÃÂÃÂ A Stairway to Heaven in the Middle of Nowhere",
    "Joseph Interprets Pharaoh's Dreams ÃÂ¢ÃÂÃÂ A Prisoner Who Saved an EMPIRE",
    "Joseph Forgives His Brothers ÃÂ¢ÃÂÃÂ They Sold Him. He Saved Them Anyway",
    "Baby Moses in the Basket ÃÂ¢ÃÂÃÂ Hidden in a River to Escape a KING",
    "The Burning Bush ÃÂ¢ÃÂÃÂ A Fire That Would Not Burn Out",
    "Manna From Heaven ÃÂ¢ÃÂÃÂ Bread That Fell From the Sky Every Morning",
    "Water From the Rock ÃÂ¢ÃÂÃÂ Moses Struck a Stone and a River Came Out",
    "The Twelve Spies ÃÂ¢ÃÂÃÂ Ten Saw Giants. Two Saw God",
    "Rahab and the Scarlet Cord ÃÂ¢ÃÂÃÂ The Outsider Who Saved Two Spies",
    "Hannah's Prayer ÃÂ¢ÃÂÃÂ She Begged God for a Son and Gave Him Back",
    "David and Jonathan ÃÂ¢ÃÂÃÂ The Friendship That Defied a KING",
    "David Spares Saul in the Cave ÃÂ¢ÃÂÃÂ He Had One Chance to Kill His Enemy",
    "Naaman Washes in the River ÃÂ¢ÃÂÃÂ A General Too PROUD to Be Healed",
    "The Widow's Oil ÃÂ¢ÃÂÃÂ One Jar That Would Not Run Empty",
    "The Floating Axe Head ÃÂ¢ÃÂÃÂ Iron That Rose Out of the Water",
    "Hezekiah and the Sundial ÃÂ¢ÃÂÃÂ The King Who Made a Shadow Go BACKWARD",
    "Job ÃÂ¢ÃÂÃÂ He Lost Everything and Still Would Not Curse God",
    "The Valley of Dry Bones ÃÂ¢ÃÂÃÂ A Field of Skeletons That Stood Back Up",
    "The Writing on the Wall ÃÂ¢ÃÂÃÂ A Hand Appeared and Wrote a King's DOOM",
    "The Woman at the Well ÃÂ¢ÃÂÃÂ A Stranger Who Knew Her Entire Life",
    "Nicodemus ÃÂ¢ÃÂÃÂ The Leader Who Came to Jesus in the DARK",
    "The Man Lowered Through the Roof ÃÂ¢ÃÂÃÂ Four Friends Who Tore Open a House",
    "Jairus' Daughter ÃÂ¢ÃÂÃÂ She Was Already Dead When Jesus Arrived",
    "The Ten Lepers ÃÂ¢ÃÂÃÂ Ten Were Healed. Only ONE Came Back",
    "Blind Bartimaeus ÃÂ¢ÃÂÃÂ They Told Him to Be Quiet. He Shouted LOUDER",
    "The Widow's Mite ÃÂ¢ÃÂÃÂ The Smallest Gift That Meant the MOST",
    "The Rich Young Ruler ÃÂ¢ÃÂÃÂ He Had Everything and Walked Away SAD",
    "Philip and the Ethiopian ÃÂ¢ÃÂÃÂ A Chariot Stopped in the Middle of the Desert",
    "Peter's Escape From Prison ÃÂ¢ÃÂÃÂ Chains Fell Off While the Guards SLEPT",
]

# Topic mix is intentionally weighted:
#   ~55% dark-behavior / personality / manipulation (1.3%+ sub conversion in Apr data)
#   ~30% cognitive biases reframed with relational or behavioral stakes
#   ~15% classic experiments and uncomfortable-truth topics
# Weak-converting topics from the original list (Mere Exposure, Cocktail Party,
# Illusion of Transparency, abstract bias labels) have been dropped.

TMF_TOPICS = [
    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Dark behavior / personality / manipulation (high sub conversion) ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    "The Dark Triad ÃÂ¢ÃÂÃÂ Why Some People Charm You While Planning to Hurt You",
    "What Narcissists, Psychopaths and Sociopaths Actually Want From You",
    "Gaslighting ÃÂ¢ÃÂÃÂ The Manipulation Most Victims Never See Coming",
    "Love Bombing ÃÂ¢ÃÂÃÂ The Red Flag That Feels Like Romance",
    "Why Narcissists Target Empaths (And How They Pick Them)",
    "How Trauma Bonds Trap Victims With Their Abusers",
    "Why Charming People Are Often the Most Dangerous",
    "Why Abusers Always Apologize Before They Do It Again",
    "The 4 Tactics Every Cult Leader Uses On Their Followers",
    "The Psychology of Liars ÃÂ¢ÃÂÃÂ 4 Tells That Give Them Away",
    "Dehumanization ÃÂ¢ÃÂÃÂ How Ordinary People Become Capable of Cruelty",
    "The Milgram Experiment ÃÂ¢ÃÂÃÂ Why 65% of People Will Hurt a Stranger",
    "The Stanford Prison Experiment ÃÂ¢ÃÂÃÂ What Power Does to Good People",
    "How People Justify Cheating, Stealing, and Lying to Themselves",
    "Why You're Drawn to People Who Treat You Poorly",
    "The Hidden Reason Some People Enjoy Others' Failure",
    "Why Predators Always Test You Before They Strike",

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Cognitive biases reframed with behavioral stakes ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    "Why One Bad Thing Erases Ten Good Things You've Done",
    "Why the Least Skilled People Are the Most Confident",
    "Why You Can't Let Go of Bad Decisions You've Already Made",
    "Why Facts Make People Believe Their Lies Even Harder",
    "Why You Think Everyone Secretly Agrees With You",
    "Why You Feel Guilty for Things That Aren't Your Fault",
    "Why You Care What Strangers Think (Even Though You Shouldn't)",
    "Why You Overestimate How Much Others Notice Your Mistakes",
    "Why You Feel Obligated to People Who Are Mean to You",
    "Why You're Nicer to Strangers Than to People You Love",
    "Why You Always Underestimate How Long Things Will Take",
    "Why You Regret Things You DIDN'T Do More Than Things You Did",
    "Why You Don't Help Even When You Want To (Bystander Effect)",
    "Why You Obey People in Positions of Power ÃÂ¢ÃÂÃÂ Even Bad Ones",
    "Why The First Number You Hear Changes Every Decision You Make",
    "Why You Only See Evidence That Proves You Right",
    "Why You Judge Other People Harsher Than You Judge Yourself",
    "Why You Feel Compelled to Return Favors ÃÂ¢ÃÂÃÂ Even From Bad People",
    "Why Your Brain Only Sees What It Wants To See",
    "Why You Keep Going Back to Things You Know Are Bad For You",

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Uncomfortable-truth / dark manipulation ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    "Why Most People Will Lie to Your Face and Believe They're Honest",
    "Why You Act Like a Completely Different Person Around Different People",
    "Why Smart People Still Make The Same Dumb Mistake Twice",
    "Why Narcissists Always Come Back After You Cut Them Off",
    "Why People Who Hurt You Act Like They're the Victim",
    "The Reason Nice People Are the Easiest to Manipulate",
    "Why You Freeze When Someone Confronts You With a Lie",
    "How Manipulators Use Silence as a Weapon Against You",
    "Why You Can't Trust Someone Who Never Admits They're Wrong",
    "Why Abusers Always Make You Feel Responsible for Their Behavior",
    "The Psychological Trick That Makes You Defend People Who Hurt You",
    "Why Dangerous People Always Seem Completely Normal at First",
    # Retired (soft behavioral, underperformed): procrastination, imposter syndrome,
    # planning fallacy, regret, tiredness ÃÂ¢ÃÂÃÂ these drift away from dark psychology core.

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Cognitive bias + relatable behavior hybrids (added May 2026) ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    # Analytics confirmed: psychological mechanism framed as "Why You" behavior
    # outperforms pure toxic-relationship angles. Top performers blend both.
    "Why You Believe Lies You've Heard Twice ÃÂ¢ÃÂÃÂ The Illusory Truth Effect",
    "Why Your Brain Ignores Logic When You're Emotionally Invested",
    "Why You Trust Someone More Just Because They Sound Confident",
    "Why You're Easier to Manipulate When You Think You're Immune",
    "Why You Give Away Your Power Without Realizing It",
    "Why You Misread Silence as Approval ÃÂ¢ÃÂÃÂ And Manipulators Know It",
    "Why Smart People Are the Easiest to Fool With a Good Story",
    "Why You Remember Humiliation More Vividly Than Praise",
    "Why Being Watched Makes You Behave Differently ÃÂ¢ÃÂÃÂ Even When You're Alone",
    "Why Your Brain Can't Tell the Difference Between Rejection and Physical Pain",
    "Why You Automatically Trust People Who Share One Thing in Common With You",
    "Why You Work Harder to Keep Something Than You Ever Did to Get It",
    "Why You Let People Interrupt You ÃÂ¢ÃÂÃÂ And Why It's Not About Politeness",
    "Why You Assume Everyone Can See How Anxious You Really Are",
]

# --- Task 4 test (weekly review Jul 19 2026): reversible 1-week concept-name
# title exception for exactly these 2 videos. Data is genuinely mixed -- best
# CTR this window (7.69%) was a concept-name title ("The Illusory Truth Effect
# Explained"), but Apr 2026 data showed concept-name/jargon titles usually
# bomb ("Pseudocertainty Effect Unveiled" 19 views, "Anchoring Bias" 7 views).
# This is a controlled test, NOT a formula switch -- both titles vetted
# against the full 228-video history for duplicates.
# TO REVERT: set TMF_CONCEPT_NAME_TEST_ENABLED = False (single flag; nothing
# else needs to change -- title_passes_tmf_rules() falls back to requiring
# "Why You"/"Why Your" for every title, same as before this test).
TMF_CONCEPT_NAME_TEST_ENABLED = True
TMF_CONCEPT_NAME_TEST_TITLES = {
    "The Chaos-Chemistry Confusion Explained",
    "The Sunk-Cost Apology Trap Explained",
}
if TMF_CONCEPT_NAME_TEST_ENABLED:
    TMF_TOPICS.extend(sorted(TMF_CONCEPT_NAME_TEST_TITLES))

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ BSG Tier 1 stories (proven top performers ÃÂ¢ÃÂÃÂ weighted 3ÃÂÃÂ in topic selection) ÃÂ¢ÃÂÃÂ
BSG_TIER1_KEYWORDS = [
    "noah", "david vs goliath", "moses parted", "birth of jesus",
    "daniel in the lion", "jonah", "joseph's coat", "adam and eve",
    "creation story", "easter story", "christmas story", "lazarus",
    "jesus walks on water", "jesus feeds 5000", "shadrach",
    "joshua and the walls", "elijah on mount carmel",
]

def _bsg_story_tier(topic: str) -> int:
    """Return 1 (Tier 1, weight 3ÃÂÃÂ) or 2 (other, weight 1ÃÂÃÂ)."""
    tl = topic.lower()
    for kw in BSG_TIER1_KEYWORDS:
        if kw in tl:
            return 1
    return 2


_BSG_NAME_SPLIT_RE = _re_imports.compile(
    "\\s*(?:\u2014|\u2013|-|\u00c3\u0083\u00c2\u00a2\u00c3\u0082\u00c2\u0080\u00c3\u0082\u00c2\u0094)\\s*"
)
# Matches any dash-style separator between story name and hook: em-dash, en-dash,
# hyphen, or the legacy mojibake-corrupted em-dash sequence baked into some older
# log entries. Fixed Jul 7 2026 -- the old version split on a literal corrupted
# string, which only matched already-corrupted text and silently failed on
# cleanly-encoded (normal) topic strings, breaking dedup for fresh topics.


class TopicBankExhausted(RuntimeError):
    """Every topic in a channel's bank has already been published.

    Raised instead of silently recycling the bank. Callers should treat this as
    a clean skip (exit 0), not a failure -- posting nothing is the correct
    outcome when the only alternative is posting a duplicate.
    """


def _bsg_story_name(topic: str) -> str:
    """Extract core story name for dedup (text before the first dash separator)."""
    return _BSG_NAME_SPLIT_RE.split(topic, maxsplit=1)[0].strip().lower()


# Canonical slug map: catches AI-generated title variations for the same story.
# Key = canonical slug, value = list of substrings that map to it.
# NOTE (Jul 19 2026 weekly review): "creation story" and "adam and eve" are both
# Tier 1 keywords (BSG_TIER1_KEYWORDS above) but were missing from this table --
# a code comment near _bsg_story_ever_posted() even referenced "Creation Story"
# as a known gap that was never actually closed. Without a slug entry, dedup
# fell back to exact-text name matching, which is fragile against any wording
# drift. Confirmed leak: Creation Story published 3x (weekly review Jul 19 2026).
_BSG_STORY_SLUGS: dict[str, list[str]] = {
    "creation-story":      ["creation story", "how god made everything", "six days of creation",
                            "made everything in 6 days", "made the world in six days",
                            "made the world in 6 days"],
    "adam-eve":            ["adam and eve", "garden of eden"],
    "daniel-lions-den":    ["daniel in the lion", "daniel's lion", "daniel and the lion"],
    "feeding-5000":        ["feeding 5,000", "feeding 5000", "jesus feeds 5,000", "jesus feeds 5000",
                            "feeding the 5,000", "feeds 5000", "feeds 5,000"],
    "good-samaritan":      ["good samaritan"],
    "prodigal-son":        ["prodigal son"],
    "moses-red-sea":       ["moses parts the red sea", "moses and the red sea", "moses red sea",
                            "parts the red sea", "red sea crossing"],
    "walls-of-jericho":    ["walls of jericho", "joshua's jericho", "joshua and the walls",
                            "wall of jericho", "jericho wall"],
    "david-goliath":       ["david and goliath", "david vs goliath", "david versus goliath"],
    "elijah-fire":         ["elijah's fiery", "elijah on mount carmel", "elijah and the fire",
                            "elijah's fire", "fire from heaven", "fiery challenge", "fiery showdown",
                            "elijah's challenge"],
    "noahs-ark":           ["noah's ark"],
    "deborah-judge":       ["deborah the judge", "deborah: the brave", "deborah brave judge"],
    "joseph-coat":         ["joseph's coat", "joseph and the coat", "coat of many colors"],
    "samson-strength":     ["samson and the lion", "samson's strength", "samson's incredible",
                            "samson's incredible strength"],
    "samson-chains":       ["samson breaks his chains", "samson breaks the chains",
                            "samson breaks", "samson and delilah"],
    "elisha-oil":          ["elisha's oil", "elisha's impossible oil"],
    "zacchaeus":           ["zacchaeus"],
    "ten-commandments":    ["ten commandments", "moses & the ten", "moses and the ten"],
    "ten-plagues":         ["ten plagues", "the plagues of egypt", "plagues of egypt",
                            "ten plagues of egypt", "god's devastating", "plague of frogs",
                            "plague of locusts", "plague of darkness"],
    "birth-of-jesus":      ["birth of jesus", "jesus is born", "christmas bible story",
                            "christmas story"],
    "easter-story":        ["easter story", "resurrection of jesus", "the resurrection"],
    "jonah-whale":         ["jonah and the whale", "jonah swallowed", "jonah in the whale",
                            "jonah whale", "swallowed by the whale"],
    "shadrach-furnace":    ["shadrach in the fiery furnace", "shadrach meshach abednego",
                            "fiery furnace", "thrown into a fiery furnace"],
    "jesus-calms-storm":   ["jesus calms the storm", "calms the storm", "jesus calms storm",
                            "storm on the sea", "peace be still"],
    "elijah-ravens":       ["elijah fed by ravens", "elijah and the ravens", "fed by ravens"],
    "jacob-wrestles":      ["jacob wrestles", "jacob and the angel", "wrestles an angel",
                            "wrestles with god"],
    "paul-silas-prison":   ["paul and silas in prison", "paul and silas", "chains fell off"],
    "jesus-walks-water":   ["jesus walks on water", "walks on water", "peter walks on water"],
    "lazarus":             ["lazarus raised", "raising of lazarus", "lazarus from the dead",
                            "lazarus dead 4 days"],
    "gideon":              ["gideon's 300", "gideon and his", "gideon's army"],
    "joshua-stops-sun":    ["joshua stops the sun", "sun stood still", "god made time stand still"],
    # ---- Added Aug 23 2026 with the bank refill -------------------------
    "cain-abel":           ["cain and abel"],
    "jacobs-ladder":       ["jacob's ladder", "stairway to heaven"],
    "joseph-pharaoh":      ["joseph interprets", "pharaoh's dreams"],
    "joseph-forgives":     ["joseph forgives"],
    "baby-moses":          ["baby moses", "moses in the basket"],
    "burning-bush":        ["burning bush"],
    "manna":               ["manna from heaven", "bread from heaven"],
    "water-from-rock":     ["water from the rock"],
    "twelve-spies":        ["twelve spies", "12 spies"],
    "rahab":               ["rahab"],
    "hannah-prayer":       ["hannah's prayer"],
    "david-jonathan":      ["david and jonathan"],
    "david-spares-saul":   ["david spares saul", "saul in the cave"],
    "naaman":              ["naaman"],
    "elisha-oil":          ["elisha's oil", "elisha's impossible oil", "the widow's oil"],
    "floating-axe":        ["floating axe", "axe head"],
    "hezekiah-sundial":    ["hezekiah and the sundial", "hezekiah"],
    "job":                 ["job"],
    "dry-bones":           ["valley of dry bones", "dry bones"],
    "writing-on-wall":     ["writing on the wall", "belshazzar"],
    "woman-at-well":       ["woman at the well"],
    "nicodemus":           ["nicodemus"],
    "paralytic-roof":      ["lowered through the roof", "through the roof"],
    "jairus-daughter":     ["jairus"],
    "ten-lepers":          ["ten lepers", "10 lepers"],
    "bartimaeus":          ["bartimaeus"],
    "widows-mite":         ["widow's mite"],
    "rich-young-ruler":    ["rich young ruler"],
    "philip-ethiopian":    ["philip and the ethiopian", "ethiopian eunuch"],
    "peter-prison-escape": ["peter's escape", "peter in prison"],
    # ---- Gaps that let real duplicates through (Aug 23 2026 audit) -------
    # These stories published 2-4x each because no slug mapped them together.
    "paul-damascus":       ["paul on the road to damascus", "road to damascus",
                            "saul's conversion", "saul of tarsus"],
    "last-supper":         ["the last supper", "last supper"],
    "crucifixion":         ["the crucifixion", "crucifixion"],
}


def _bsg_story_slug(topic: str) -> str:
    """Return a canonical story slug for dedup. Catches AI title variations."""
    name = _bsg_story_name(topic)
    for slug, aliases in _BSG_STORY_SLUGS.items():
        if any(alias in name for alias in aliases):
            return slug
    return name  # fallback: use normalized name as-is


def _bsg_story_posted_recently(topic: str, days: int = 60) -> bool:
    """True if the same Bible story (by canonical slug) was posted within `days` days.
    Uses per-channel log for reliable persistence across GH Actions runs.
    NOTE: kept for backward compatibility ÃÂ¢ÃÂÃÂ new code should call _bsg_story_ever_posted()."""
    log = _load_channel_log("bsg")
    slug = _bsg_story_slug(topic)
    cutoff = datetime.now(ZoneInfo("America/Chicago")) - timedelta(days=days)
    for post in log.get("posts", []):
        if post.get("channel") != "bsg":
            continue
        try:
            post_dt = datetime.strptime(post.get("posted_at", ""), "%Y-%m-%d %H:%M:%S")
            post_dt = post_dt.replace(tzinfo=ZoneInfo("America/Chicago"))
        except ValueError:
            continue
        if post_dt < cutoff:
            continue
        if _bsg_story_slug(post.get("topic", "")) == slug:
            return True
    return False


def _bsg_story_ever_posted(topic: str) -> bool:
    """True if this Bible story (by canonical slug) has EVER been posted on BSG.
    Enforces the hard rule: one canonical version per story, ever.
    Replaces the 60-day rolling window that allowed Daniel 4x / Jericho 5x / David 4x."""
    log = _load_channel_log("bsg")
    slug = _bsg_story_slug(topic)
    for post in log.get("posts", []):
        if post.get("channel") != "bsg":
            continue
        if _bsg_story_slug(post.get("topic", "")) == slug:
            return True
    # Fixed Jul 7 2026: "posts" (structured, timestamped) lagged behind the
    # legacy flat "bsg" topic list -- mark_posted() writes both, but "posts"
    # was missing real entries (e.g. Creation Story, Easter Story), letting
    # this guard miss duplicates it was built to stop. Check both lists.
    for past_topic in log.get("bsg", []):
        if _bsg_story_slug(past_topic) == slug:
            return True
    return False


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ TMF 14-day concept-level dedup ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
# Window raised from 7ÃÂ¢ÃÂÃÂ14 days: at 2x/day (14 posts/week), a 7-day window was
# too narrow ÃÂ¢ÃÂÃÂ exact-title duplicates slipped through on the boundary day.

_TMF_STOP_WORDS = {
    "your", "you're", "that", "they", "their", "with", "from", "have", "this",
    "even", "most", "some", "when", "what", "will", "more", "less", "just",
    "very", "always", "never", "every", "been", "after", "before", "into",
    "people", "person", "someone", "other", "about", "while", "think", "feel",
}

def _topic_keywords(topic: str) -> set:
    """Extract meaningful 5+ char keywords from a topic string."""
    words = _re_imports.findall(r"[a-z]+", topic.lower())
    return {w for w in words if len(w) >= 5 and w not in _TMF_STOP_WORDS}


def _mz_company_posted_recently(topic: str, days: int = 30) -> bool:
    """True if a video about the same company was posted on MZ within `days` days.
    Extracts the company name from the topic string (format: 'Company — angle' or
    'Company bankruptcy/scandal/etc') and blocks repeats within the window.
    Prevents duplicate titles like 'The FBI Raid That Exposed HealthSouth' (posted twice).
    """
    import re as _re2
    log = _load_channel_log("mz")
    # Extract company slug: take first 2 significant words from topic
    words = _re2.findall(r"[A-Za-z]{3,}", topic)
    # Skip generic business words
    skip = {"the", "how", "one", "that", "this", "from", "into", "with", "its",
            "was", "and", "for", "billion", "million", "nearly", "almost",
            "saved", "killed", "exposed", "destroyed", "crashed", "collapsed",
            "survived", "failed", "went", "built", "lost", "bet", "deal",
            "company", "corp", "inc", "ltd"}
    sig = [w.lower() for w in words if w.lower() not in skip]
    if not sig:
        return False
    # Use first meaningful word as company anchor (e.g. "HealthSouth", "Blockbuster")
    company_anchor = sig[0]
    cutoff = datetime.now(ZoneInfo("America/Chicago")) - timedelta(days=days)
    for post in log.get("posts", []):
        if post.get("channel") != "mz":
            continue
        try:
            post_dt = datetime.strptime(post.get("posted_at", ""), "%Y-%m-%d %H:%M:%S")
            post_dt = post_dt.replace(tzinfo=ZoneInfo("America/Chicago"))
        except ValueError:
            continue
        if post_dt < cutoff:
            continue
        past_topic = post.get("topic", "").lower()
        past_title = post.get("title", "").lower()
        if company_anchor in past_topic or company_anchor in past_title:
            return True
    return False


def _tmf_topic_too_similar_to_recent(topic: str, days: int = 14) -> bool:
    """True if this topic shares ÃÂ¢ÃÂÃÂ¥2 concept keywords with any TMF post in the last 14 days.
    Prevents toxic/guilt/manipulation cluster saturation. Uses per-channel log."""
    log = _load_channel_log("tmf")
    cutoff = datetime.now(ZoneInfo("America/Chicago")) - timedelta(days=days)
    candidate_kw = _topic_keywords(topic)
    if not candidate_kw:
        return False
    for post in log.get("posts", []):
        if post.get("channel") != "tmf":
            continue
        try:
            posted_str = post.get("posted_at", "")
            post_dt = datetime.strptime(posted_str, "%Y-%m-%d %H:%M:%S")
            post_dt = post_dt.replace(tzinfo=ZoneInfo("America/Chicago"))
        except ValueError:
            continue
        if post_dt < cutoff:
            continue
        recent_kw = _topic_keywords(post.get("topic", ""))
        if len(candidate_kw & recent_kw) >= 2:
            return True
    return False


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Topic Log ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

def _channel_log_file(channel: str) -> Path:
    """Return the per-channel log file path."""
    return BSG_LOG_FILE if channel == "bsg" else TMF_LOG_FILE if channel == "tmf" else LOG_FILE


def _load_channel_log(channel: str) -> dict:
    """Load per-channel log, merging any legacy entries from the shared log."""
    ch_file = _channel_log_file(channel)
    data: dict = {"posts": [], channel: []}
    if ch_file.exists():
        try:
            data = json.loads(ch_file.read_text())
        except Exception:
            pass
    # Backwards compat: pull in any entries from shared log not yet in channel file
    if LOG_FILE.exists():
        try:
            shared = json.loads(LOG_FILE.read_text())
            existing_ats = {p.get("posted_at") for p in data.get("posts", [])}
            for p in shared.get("posts", []):
                if p.get("channel") == channel and p.get("posted_at") not in existing_ats:
                    data.setdefault("posts", []).append(p)
            existing_topics = set(data.get(channel, []))
            for t in shared.get(channel, []):
                if t not in existing_topics:
                    data.setdefault(channel, []).append(t)
        except Exception:
            pass
    return data


def _save_channel_log(channel: str, log: dict) -> None:
    """Save to per-channel file (primary) and update shared log (compat)."""
    _channel_log_file(channel).write_text(json.dumps(log, indent=2))
    # Keep shared log updated for any tooling that reads it
    try:
        shared: dict = {"bsg": [], "tmf": [], "posts": []}
        if LOG_FILE.exists():
            shared = json.loads(LOG_FILE.read_text())
        shared_ats = {p.get("posted_at") for p in shared.get("posts", []) if p.get("channel") == channel}
        for p in log.get("posts", []):
            if p.get("posted_at") not in shared_ats:
                shared.setdefault("posts", []).append(p)
        shared[channel] = log.get(channel, [])
        LOG_FILE.write_text(json.dumps(shared, indent=2))
    except Exception:
        pass


def load_log() -> dict:
    """Load the shared topic usage log (legacy ÃÂ¢ÃÂÃÂ new code uses _load_channel_log)."""
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text())
        except Exception:
            pass
    return {"bsg": [], "tmf": [], "posts": []}


def save_log(log: dict) -> None:
    LOG_FILE.write_text(json.dumps(log, indent=2))


def pick_topic(channel: str) -> str:
    """Pick a topic not yet used in this cycle, applying channel-specific guardrails.

    BSG: 60-day story slug dedup + Tier 1 weighted selection (proven stories 3ÃÂÃÂ more likely).
    TMF: 14-day concept-overlap dedup (prevents toxic/guilt cluster saturation).
    Both now use per-channel log files for reliable GH Actions persistence.
    """
    log = _load_channel_log(channel)
    topics = BSG_TOPICS if channel == "bsg" else TMF_TOPICS
    used = set(log.get(channel, []))

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ First pass: full guard (cycle dedup + channel-specific dedup) ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    if channel == "bsg":
        available = [
            t for t in topics
            if t not in used and not _bsg_story_ever_posted(t)
        ]
    elif channel == "tmf":
        available = [
            t for t in topics
            if t not in used and not _tmf_topic_too_similar_to_recent(t, days=14)
        ]
    elif channel == "mz":
        # MZ: 30-day company-level dedup — prevents same company appearing twice
        available = [
            t for t in topics
            if t not in used and not _mz_company_posted_recently(t, days=30)
        ]
    else:
        available = [t for t in topics if t not in used]

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Cycle reset: all topics used (or all exhausted by strict dedup) ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    if 0 < len(available) <= 5:
        print(f"  [!] BSG TOPIC BANK LOW -- only {len(available)} unpublished "
              f"story/stories left. Add more to BSG_TOPICS before it hits zero.")

    if not available:
        print(f"  ÃÂ°ÃÂÃÂÃÂ All {len(topics)} topics used (or filtered by dedup) ÃÂ¢ÃÂÃÂ starting new cycle!")
        log[channel] = []
        _save_channel_log(channel, log)
        # Second pass: loosen cycle dedup only ÃÂ¢ÃÂÃÂ keep slug/concept dedup
        # BSG: permanent dedup is intentional ÃÂ¢ÃÂÃÂ if all stories exhausted, add new ones to BSG_TOPICS
        if channel == "bsg":
            available = [t for t in topics if not _bsg_story_ever_posted(t)]
        elif channel == "tmf":
            available = [t for t in topics if not _tmf_topic_too_similar_to_recent(t, days=14)]
        elif channel == "mz":
            available = [t for t in topics if not _mz_company_posted_recently(t, days=30)]
        if not available:
            # Aug 23 2026 -- this used to be:
            #     available = topics[:]  # Last resort: pick from full bank
            # which silently disabled dedup once the bank ran dry. BSG hit zero
            # eligible topics on Aug 2 2026 and every run since drew uniformly
            # from all 46 topics with the ever-block discarded. That is how
            # "The Birth of Jesus" published three times in five days and why
            # 22% of BSG's catalog is duplicates (TMF 5%, MZ 4%).
            # MZ deleted this same anti-pattern on Aug 2 (TopicBankExhausted).
            # Publishing nothing beats publishing a duplicate -- repetitive
            # uploads are a live termination risk under YouTube's "Generic or
            # Repetitive Content" policy.
            if channel == "bsg":
                raise TopicBankExhausted(
                    f"BSG: all {len(topics)} stories have already been published. "
                    f"Add new entries to BSG_TOPICS (and a slug to _BSG_STORY_SLUGS) "
                    f"-- refusing to post a duplicate."
                )
            available = topics[:]  # TMF/MZ use rolling windows; recycling is safe

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ BSG: Tier 1 weighted selection ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    if channel == "bsg":
        weights = [3 if _bsg_story_tier(t) == 1 else 1 for t in available]
        chosen = random.choices(available, weights=weights, k=1)[0]
        tier_label = "Tier 1 (3ÃÂÃÂ)" if _bsg_story_tier(chosen) == 1 else "Tier 2"
        print(f"  ÃÂ°ÃÂÃÂÃÂ BSG topic selected [{tier_label}]: {chosen[:70]}...")
        return chosen

    return random.choice(available)


def mark_posted(channel: str, topic: str, title: str, url: str) -> None:
    """Record a successful post so the topic is not repeated.
    Writes to per-channel log file (reliable GH Actions persistence)."""
    log = _load_channel_log(channel)
    if channel not in log:
        log[channel] = []
    if topic not in log[channel]:
        log[channel].append(topic)
    if "posts" not in log:
        log["posts"] = []
    log["posts"].append({
        "channel":   channel,
        "topic":     topic,
        "title":     title,
        "url":       url,
        "posted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_channel_log(channel, log)
    append_to_google_sheets(channel, title, url)


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Validators (post-generation guardrails) ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
# These exist because the LLM frequently violates the system-prompt rules.
# We catch the violations in code rather than trusting the model.

import re as _re

# Effect/jargon nouns the model tends to slap at the start of a title.
# If the FIRST word of a title (after "The ") matches one of these, reject.
_TMF_BANNED_LEAD_NOUNS = {
    "halo", "anchoring", "bystander", "barnum", "pseudocertainty", "negativity",
    "dunning", "confirmation", "framing", "availability", "spotlight",
    "pratfall", "ikea", "hindsight", "recency", "primacy", "endowment",
    "illusion", "mere", "cocktail", "mind",
}

# Hook phrases that are burned out / cannibalizing (Jun 7 2026 analytics).
# These may appear in a script body but NEVER as the title's core hook.
_TMF_BANNED_HOOK_PHRASES = [
    "toxic manipulator",
    "toxic manipulators",
    "toxic relationship",
    "toxic relationships",
    "toxic people",
    "charming manipulator",
    "manipulation red flags",
]

def _contains_banned_hook(title: str) -> bool:
    """True if title contains a burned-out hook phrase (case-insensitive)."""
    t = title.lower()
    return any(phrase in t for phrase in _TMF_BANNED_HOOK_PHRASES)

def _normalize_title(t: str) -> str:
    """Lowercase + strip punctuation/whitespace for fuzzy comparison."""
    s = (t or "").lower()
    s = _re.sub(r"(?<=[0-9]),(?=[0-9])", "", s)  # "5,000" -> "5000"
    s = _re.sub(r"[^a-z0-9 ]+", " ", s)
    return _re.sub(r"\s+", " ", s).strip()

# Stopwords stripped before duplicate-detection keyword comparison. Includes
# generic connectors AND per-channel branding words (kids/bible/story/garden)
# that appear in every BSG title and would otherwise inflate overlap scores.
_TITLE_DEDUP_STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "with",
    "why", "your", "you", "kids", "bible", "story", "stories", "garden",
}

def _title_keyword_set(t: str) -> set:
    """Emoji/punctuation-stripped, stopword-filtered, lightly-stemmed keyword
    set used for fuzzy duplicate detection.

    Fixes confirmed gaps in the old exact-string-after-normalize check:
    "&" vs "and" ("Ruth & Naomi" vs "Ruth and Naomi"), emoji variants, plural
    or possessive drift ("Daniel's Lion Den" vs "Daniel in the Lion's Den"),
    and reworded-but-same-story titles ("Jesus Feeds 5000" vs "Feeding the
    5,000"). Confirmed root cause of BSG republishing the same stories 2-5x
    within a single 28-day window (Jul 5 2026 analytics review).
    """
    norm = _normalize_title(t)
    kws = set()
    for w in norm.split():
        if w in _TITLE_DEDUP_STOPWORDS or len(w) < 3:
            continue
        if w.endswith("ing") and len(w) > 5:
            w = w[:-3]
        elif w.endswith("s") and len(w) > 4:
            w = w[:-1]
        kws.add(w)
    return kws

def _titles_are_duplicate(a: str, b: str, threshold: float = 0.6) -> bool:
    """True if two titles are the same story/concept: exact match after basic
    normalization, OR high keyword overlap (Jaccard similarity) once emoji,
    punctuation, stopwords, and light plural/possessive stemming are removed.
    """
    na, nb = _normalize_title(a), _normalize_title(b)
    if na and na == nb:
        return True
    ka, kb = _title_keyword_set(a), _title_keyword_set(b)
    if not ka or not kb:
        return False
    return len(ka & kb) / len(ka | kb) >= threshold

def title_passes_tmf_rules(title: str) -> tuple[bool, str]:
    """
    Returns (ok, reason). False reason gets fed back into the retry prompt.
    Mirrors the TITLE RULES inside the system prompt ÃÂ¢ÃÂÃÂ these are enforced here
    because gpt-4o regularly ignores them otherwise.
    """
    if not title or not title.strip():
        return False, "empty title"
    t = title.strip()

    # Task 4 test exception (weekly review Jul 19 2026): 2 explicitly flagged
    # concept-name titles bypass the "Why You" + colon rules below. See
    # TMF_CONCEPT_NAME_TEST_ENABLED above to revert with a single flag flip.
    if TMF_CONCEPT_NAME_TEST_ENABLED and t in TMF_CONCEPT_NAME_TEST_TITLES:
        if len(t) > 65:
            return False, f"title too long ({len(t)} chars; keep under 60)"
        return True, "TASK4_TEST_EXCEPTION: concept-name format (reversible 1-week test)"


    if len(t) > 65:
        return False, f"title too long ({len(t)} chars; keep under 60)"

    # MUST start with "Why You" or "Why Your" ÃÂ¢ÃÂÃÂ data shows this pattern drives 400-1300 views
    # vs "The [noun]" or other patterns averaging <50 views. Enforced May 6 2026.
    t_lower = t.lower()
    if not (t_lower.startswith("why you") or t_lower.startswith("why your")):
        return False, (
            'title must start with "Why You" or "Why Your" ÃÂ¢ÃÂÃÂ '
            'e.g. "Why You Stay Loyal to Mean People". '
            'Data: "Why You..." titles avg 400-1300 views; other patterns avg <50 views. '
            'Rewrite as "Why You [verb] [observable behavior]".'
        )

    # No colon mid-title ÃÂ¢ÃÂÃÂ kills CTR ("Why You're Right: The Mind Trap" flopped)
    if ":" in t:
        return False, 'no colon in title ÃÂ¢ÃÂÃÂ "Why You [behavior]" only, no subtitle after colon'

    # Jun 7 2026: ban burned-out hook phrases as title hooks (toxic manipulator cluster)
    if _contains_banned_hook(t):
        banned = next(p for p in _TMF_BANNED_HOOK_PHRASES if p in t.lower())
        return False, (
            f'banned hook phrase in title: "{banned}". '
            'This cluster is burned out (380ÃÂ¢ÃÂÃÂ291ÃÂ¢ÃÂÃÂ185 view decay). '
            'Rewrite around a specific behavior ÃÂ¢ÃÂÃÂ e.g. "Why You Trust People Who Lie to You."'
        )

    return True, ""

def script_word_count_ok(script: dict) -> tuple[bool, int]:
    """Total narration words must land in 140ÃÂ¢ÃÂÃÂ180 (ÃÂ¢ÃÂÃÂ42ÃÂ¢ÃÂÃÂ55 sec at ~3.3 words/sec TTS rate).
    Recalibrated Jun 7 2026: May 10ÃÂ¢ÃÂÃÂJun 7 analytics show top-7 videos all 42ÃÂ¢ÃÂÃÂ55s.
    Longer videos (65ÃÂ¢ÃÂÃÂ80s) are underperforming relative to that cohort.
    Previous target was 300ÃÂ¢ÃÂÃÂ370w (May 6 2026) ÃÂ¢ÃÂÃÂ superseded by this window's data.
    """
    total = 0
    for scene in script.get("scenes", []):
        total += len((scene.get("narration") or "").split())
    return (140 <= total <= 180), total

def script_word_count_ok_bsg(script: dict) -> tuple[bool, int]:
    """BSG narration gate: 100-130 words (~45-55s at Jenny's ~2.4 w/s kids-story pacing).
    Added Jul 12 2026 (W1-C): BSG previously had NO length gate -- published Shorts
    ran 68-97s while the shared prompt assumed TMF's 3.3 w/s rate. Ground truth:
    124w script published at 51s (2.43 w/s). 100w = ~41s, 130w = ~54s."""
    total = 0
    for scene in script.get("scenes", []):
        total += len((scene.get("narration") or "").split())
    return (100 <= total <= 130), total

def title_already_published(title: str, channel: str) -> bool:
    """Fuzzy-match the candidate title against past posts.

    Reads from the per-channel log (primary source of truth) so it stays
    accurate even when the shared auto_post_log.json lags behind due to
    concurrent GH Actions runs or merge conflicts.

    Uses _titles_are_duplicate() (keyword-overlap, not exact string match) so
    emoji variants, "&" vs "and", plurals/possessives, and reworded-but-same-
    story titles are caught -- not just byte-identical titles. Fixed Jul 5
    2026 after analytics showed near-duplicate titles slipping through on
    all three channels (worst on BSG).
    """
    log = _load_channel_log(channel)
    if not (title or "").strip():
        return False
    for post in log.get("posts", []):
        if post.get("channel") != channel:
            continue
        if _titles_are_duplicate(title, post.get("title", "")):
            return True
    return False

# Per-channel daily cap. The cron schedule already targets these counts;
# this guard exists to stop manual workflow_dispatch / re-runs from stacking
# 5ÃÂ¢ÃÂÃÂ7 videos on a single day, which Apr 2026 analytics showed dilutes the
# algorithm and tanks per-video views.
DAILY_POST_CAPS = {
    # Tightened Jul 5 2026: every channel is now scheduled for at most 1 post/day
    # (see tmf-autopost.yml / bsg-autopost.yml / mz-autopost.yml cron changes).
    # Caps stay at 1 to guard against workflow_dispatch or retries stacking extra
    # posts on top of the scheduled one.
    "tmf": 1,
    "bsg": 1,
    "mz":  1,
}

def posts_today_count(channel: str) -> int:
    """Number of successful posts for `channel` today (America/Chicago)."""
    log = load_log()
    today = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
    n = 0
    for post in log.get("posts", []):
        if post.get("channel") != channel:
            continue
        posted_at = post.get("posted_at", "")
        # posted_at format: "%Y-%m-%d %H:%M:%S" (server local). Treat the date prefix as the date.
        if posted_at.startswith(today):
            n += 1
    return n

def burst_guard_or_exit(channel: str) -> None:
    """Refuse to publish if today's count is already at the daily cap. Exits 0."""
    cap = DAILY_POST_CAPS.get(channel)
    if not cap:
        return
    today_n = posts_today_count(channel)
    if today_n >= cap:
        label = CHANNEL_LABELS.get(channel, channel)
        print(
            f"\nÃÂ°ÃÂÃÂÃÂ Burst-guard: {label} already has {today_n} successful posts today "
            f"(cap = {cap}). Skipping this run to protect algorithmic distribution.\n"
            f"   To override (rare ÃÂ¢ÃÂÃÂ e.g., recovering from a failed run), set "
            f"BURST_GUARD_OVERRIDE=1 in env."
        )
        sys.exit(0)


def generate_script_for_topic(topic: str, channel: str, num_scenes: int = 8) -> dict:
    """Generate a full video script using OpenAI (standalone, no Flask needed)."""
    if not topic or not topic.strip():
        raise ValueError("Topic cannot be empty")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found. Check GitHub secrets are set correctly.")

    if not api_key.strip():
        raise ValueError("OPENAI_API_KEY is empty. Check GitHub secret value.")

    # Channel-specific instructions
    if channel == "tmf":
        style_guide = (
            "Dark psychology / human behavior educational content for adults. "
            "Tone: calm, analytical, slightly unsettling. "
            "Image prompts MUST feature a young woman (25ÃÂ¢ÃÂÃÂ35) as the emotional focal point ÃÂ¢ÃÂÃÂ this is data-backed: female-portrait images outperform all other visuals on this channel. "
            "Each prompt should describe: (1) what the woman is doing or feeling, (2) the lighting source, (3) the environment or background. "
            "She should feel psychologically present ÃÂ¢ÃÂÃÂ pensive, guarded, introspective, or emotionally raw. Never smiling or posed. "
            "Examples: 'woman staring at her own reflection in a cracked mirror, single candle, dark room' / "
            "'woman sitting alone at a diner table at 2am, neon light through rain window, looking down' / "
            "'close-up of woman's face half in shadow, tears on cheek, blurred city lights behind her'. "
            "Style: cinematic, film noir, desaturated, photorealistic editorial photography. No text, no logos."
        )
    else:
        style_guide = (
            "Bible story / children's educational content for families with young kids. "
            "Tone: warm, wonder-filled, simple, encouraging. "
            "Image prompts should be colorful, cheerful storybook illustration style. "
            "Scene 1 MUST be a dramatic hook that stops scrolling. "
            "Scene 1 image: VISUALLY STRIKING ÃÂ¢ÃÂÃÂ bold colors, dramatic moment."
        )

    # TMF-specific retention/title rules. These are data-backed from the Mar 22 ÃÂ¢ÃÂÃÂ Apr 18
    # analytics: top 6 videos = 56% of all views; pure-jargon titles avg ~20 views;
    # 90+ sec videos avg ~40 views; False Consensus had 78.7% swipe-away at 0:32 of 1:16.
    if channel == "tmf":
        channel_rules = """
TITLE RULES (strict ÃÂ¢ÃÂÃÂ titles drive 20ÃÂÃÂ view differences in this channel):
- MUST start with "Why You" or "Why Your". This is the #1 rule. No exceptions.
- Lead with the CONTRADICTION or UNSETTLING PAYOFF ÃÂ¢ÃÂÃÂ pair a trusted/positive action with a dark outcome.
  GOOD: "Why You Trust Liars Who Feel Honest" (802 views) ÃÂ¢ÃÂÃÂ trusted action + dark outcome
  GOOD: "Why You Defend Those Who Hurt You" (598 views) ÃÂ¢ÃÂÃÂ contradiction
  BAD:  "Why You Attract Toxic Manipulators" ÃÂ¢ÃÂÃÂ flat category label, no contradiction
- Under 60 characters. Front-load the surprising word.
- No colon mid-title. If your draft doesn't start with "Why You/Your", REWRITE it.
- On TEST VEIN titles only: you may append the named effect in brackets for authority ÃÂ¢ÃÂÃÂ
  e.g. "Why You're Nicer to Strangers [Spotlight Effect]". Use sparingly to test CTR.

TOPIC SELECTION ÃÂ¢ÃÂÃÂ PILLAR MIX (enforce this ratio every batch):

  PILLAR 1 ÃÂ¢ÃÂÃÂ TRUST / DECEPTION / BETRAYAL (~40%) ÃÂ¢ÃÂÃÂ proven #1 vein
  Pattern: "Why You [trust/defend/forgive/believe] [person who does a bad thing]"
  Top performers: Trust Liars Who Feel Honest (802), Trust Those Who Never Apologize (778),
  Defend Those Who Hurt You (598), Trust Those Who Deceive (669).
  Mine: trust + calm/silence, forgive + betrayal, believe + contradiction, defend + harm.

  PILLAR 2 ÃÂ¢ÃÂÃÂ MEMORY & EMOTIONAL DISTORTION (~25%) ÃÂ¢ÃÂÃÂ proven #2 vein
  Test: why insults are remembered word-for-word, why embarrassing moments replay for years,
  false memories, hindsight bias, why one bad thing erases ten good ones, negativity bias,
  recency bias, why your worst memory feels most true.

  PILLAR 3 ÃÂ¢ÃÂÃÂ TEST VEINS (~25%) ÃÂ¢ÃÂÃÂ rotate to find the next winner
  Active rotation: cognitive biases (confirmation bias, illusory truth, framing effect),
  social hierarchy / status games, personality pathology mechanics (narcissism, psychopathy ÃÂ¢ÃÂÃÂ
  frame as "why you [behavior around them]", NOT "how to spot").

  PILLAR 4 ÃÂ¢ÃÂÃÂ SELF-PERCEPTION / SOCIAL CONTRADICTION (~10%)
  Pattern: behavior toward others that contradicts self-image.
  Proven: "Why You're Nicer to Strangers" (704 views). Mine the contradiction angle.

HARD RULES (enforced in code ÃÂ¢ÃÂÃÂ violating these triggers a retry):
  1. BANNED TITLE HOOKS: Never use toxic manipulator(s), toxic relationship(s), toxic people,
     charming manipulator, manipulation red flags as the title's core hook. Burned out.
     (May appear inside the script body ÃÂ¢ÃÂÃÂ just not in the title.)
  2. NO CONCEPT REPEATS within 30 days. Core idea must not duplicate a recent title.
  3. NO standalone time/procrastination/deadline titles ÃÂ¢ÃÂÃÂ only allowed if reframed as
     memory or identity distortion (e.g. "Why You Remember Every Task You Left Unfinished").
  4. LENGTH: 42ÃÂ¢ÃÂÃÂ55 seconds = 140ÃÂ¢ÃÂÃÂ180 narration words. Enforced by word-count validator.

HOOK RULES (first 0ÃÂ¢ÃÂÃÂ5 sec):
- Scene 1 = hook. First 3ÃÂ¢ÃÂÃÂ4 words must carry the tension. Drop the viewer mid-claim.
- BANNED openers: "Most peopleÃÂ¢ÃÂÃÂ¦", "Have you everÃÂ¢ÃÂÃÂ¦", "Did you knowÃÂ¢ÃÂÃÂ¦", "ImagineÃÂ¢ÃÂÃÂ¦"
- Open with the unsettling claim itself. Use "you" within the first two sentences.
- Scene 2 must DEEPEN or PAY OFF the hook ÃÂ¢ÃÂÃÂ never pivot or define a term.
- Never name the academic effect until scene 4 or later.

HOOK VARIANTS (REQUIRED ÃÂ¢ÃÂÃÂ produce all 3. Algorithm penalizes repeated hook patterns):
  shocking_claim   ÃÂ¢ÃÂÃÂ Flat, specific, uncomfortable truth stated as fact. No question mark.
                     Example: "You've already decided. You just don't know it yet."
  uncomfortable_question ÃÂ¢ÃÂÃÂ Second-person question the viewer can't say no to.
                     Example: "Have you noticed you work harder to keep things you hate than to gain what you want?"
  behavioral_contradiction ÃÂ¢ÃÂÃÂ Open with a paradox: two behaviors that contradict each other and both feel true.
                     Example: "The smarter someone is, the worse they are at spotting their own blind spots."

The script's Scene 1 narration = shocking_claim variant (default). Produce all 3 in hook_variants.

BODY & PAYOFF:
- Sentences average 10ÃÂ¢ÃÂÃÂ14 words. Short, punchy, spoken rhythm.
- Use "you" at least 3 times ÃÂ¢ÃÂÃÂ create personal confrontation.
- Final scene = an uncomfortable reframe. Not a motivational quote. Not a call to action.
- Leave the viewer slightly disturbed, thinking, re-examining their own behavior.

CLIFFHANGER RULE — SHORT→LONGFORM HOOK (deployed Jun 28 2026):
- NEVER name and fully explain the bias/effect in the FINAL scene. The Short ends on UNRESOLVED tension.
- Final scene states the uncomfortable truth but withholds the full mechanism — viewer must watch the full video.
- BAD ending: "This is called the Fundamental Attribution Error. Now you understand why you judge others unfairly."
- GOOD ending: "You've been blaming the wrong thing this whole time. And the people closest to you have already noticed it."
- The bias name (if used) appears MID-script, not as the payoff. Final scene = open question, not an answer.
- Goal: viewer finishes the Short knowing WHAT is happening, but needing the full video to understand WHY.
"""
    else:
        channel_rules = """
TITLE RULES (strict ÃÂ¢ÃÂÃÂ must match EXACTLY this format):
- FORMAT: [Story tension phrase] [single emoji], no channel name, no pipes
- The emoji must signal the DRAMATIC BEAT of the story ÃÂ¢ÃÂÃÂ not a generic symbol:
    ÃÂ°ÃÂÃÂÃÂ whale/sea creature  ÃÂ°ÃÂÃÂÃÂ¥ fire/furnace  ÃÂ°ÃÂÃÂÃÂº trumpet/walls  ÃÂ°ÃÂÃÂÃÂª strength/chains
    ÃÂ¢ÃÂÃÂÃÂ¯ÃÂ¸ÃÂ battle/giant  ÃÂ°ÃÂÃÂÃÂ sea/flood/storm  ÃÂ°ÃÂÃÂÃÂ´ talking animal  ÃÂ°ÃÂÃÂ¦ÃÂ lion  ÃÂ°ÃÂÃÂÃÂ¸ plague/animals
- Story name = most action/drama-forward phrasing possible. Under 40 chars before the pipe.
- GOOD examples (data-backed top performers):
  ÃÂ¢ÃÂÃÂ¢ "Balaam's Donkey ÃÂ°ÃÂÃÂÃÂ´"
  ÃÂ¢ÃÂÃÂ¢ "Daniel in the Lion's Den ÃÂ°ÃÂÃÂ¦ÃÂ"
  ÃÂ¢ÃÂÃÂ¢ "Elijah Calls Down Fire ÃÂ°ÃÂÃÂÃÂ¥"
  ÃÂ¢ÃÂÃÂ¢ "Jonah Swallowed by the Whale ÃÂ°ÃÂÃÂÃÂ"
  ÃÂ¢ÃÂÃÂ¢ "Noah's Ark ÃÂ°ÃÂÃÂÃÂ"
  ÃÂ¢ÃÂÃÂ¢ "David vs Goliath ÃÂ¢ÃÂÃÂÃÂ¯ÃÂ¸ÃÂ"
- BAD examples (confirmed 0-view format breaks ÃÂ¢ÃÂÃÂ never reproduce these):
  ÃÂ¢ÃÂÃÂ¢ "Jonah and the Whale: The Prophet Who Ran from God" ÃÂ¢ÃÂÃÂ colon/subtitle format, BANNED
  ÃÂ¢ÃÂÃÂ¢ "Paul on the Road to Damascus: The Most Dramatic Conversion" ÃÂ¢ÃÂÃÂ colon, BANNED
  ÃÂ¢ÃÂÃÂ¢ "Elisha's Impossible Oil Miracle" ÃÂ¢ÃÂÃÂ missing tail entirely, BANNED
  ÃÂ¢ÃÂÃÂ¢ "Deborah: The Brave Judge" ÃÂ¢ÃÂÃÂ missing format, BANNED
- If your title doesn't follow the EXACT format, REWRITE it. No exceptions.

STORY SELECTION ÃÂ¢ÃÂÃÂ DRAMA AND VISUAL PAYOFF FIRST (Jun 2026 analytics update):
- TIER 1 (highest-performing ÃÂ¢ÃÂÃÂ action/animal/spectacle): Balaam's Donkey, Daniel in the Lion's Den,
  Elijah Calls Down Fire, David vs Goliath, Moses Parted the Red Sea, Noah's Ark,
  Jonah Swallowed by the Whale, Samson Breaks His Chains, The Ten Plagues of Egypt,
  Jesus Calms the Storm, Shadrach in the Fiery Furnace, The Walls of Jericho Fall,
  Gideon's 300 Warriors, Joshua Stops the Sun, Jesus Feeds 5000
- TIER 2 (strong visual payoff): Lazarus Raised from the Dead, Jesus Walks on Water,
  Jacob Wrestles the Angel, Peter Walks on Water, Paul and Silas in Prison,
  Esther Saves Her People, Joseph Sold by His Brothers
- TIER 3 (use sparingly ÃÂ¢ÃÂÃÂ must reframe around a single dramatic moment): quiet/relational stories
- NEVER pick: verse cards, the Beatitudes, pure-teaching parables without physical conflict,
  out-of-season content (Christmas outside NovÃÂ¢ÃÂÃÂDec, Easter outside MarÃÂ¢ÃÂÃÂApr)
  DOCTRINE-AS-TEACHING EXCLUSION (added Jul 19 2026 -- weekly review):
  Some events have real physical drama (a death, an empty tomb, a blinding light)
  but got scripted as abstract theological reflection instead of a concrete kid's
  story, and bombed (0-1 views vs 50+ for the proven visual-narrative canon).
  NEVER pick these framings -- reuse the proven story instead, or reframe around
  ONE concrete physical moment a kid can picture:
    - The Crucifixion / Resurrection told as theology or "what this means" --
      the concrete version already exists as "The Easter Story" in the topic bank.
    - Peter's vision of Cornelius, or any "vision + instruction" story told as a
      teaching moment about inclusion/doctrine rather than a scene with people,
      places, and a physical turning point.
    - Paul's road to Damascus told as a lesson about conversion rather than the
      dramatic story already covered by "Saul's Conversion" in the topic bank.
  A vision, voice, or instruction from God is NOT enough on its own to pass the
  ACTION GATE below -- it must be paired with a concrete physical event a kid can
  picture (not just "God told him to...").

ACTION GATE (hard rule ÃÂ¢ÃÂÃÂ if a story fails this, output "has_action_gate": false and stop):
Every script MUST have ALL FOUR:
  1. A named character facing danger or an impossible situation
  2. A specific dramatic moment (the lion attacks, the walls shake, the whale swallows)
  3. A turning point where God intervenes in a physically visible, dramatic way
  4. A concrete, visible outcome (character survives / enemy falls / sea parts / fire doesn't burn)
Signal in your JSON with: "has_action_gate": true
If any of the four are absent, output "has_action_gate": false ÃÂ¢ÃÂÃÂ do not write the full script.

HOOK RULES:
- Scene 1: Drop into the peak dramatic moment. No setup. No "One day..." or "Long ago..."
- Scene 2: Deepen the stakes ÃÂ¢ÃÂÃÂ who is this person, what impossible thing is happening?
- Never open with context-setting or character backstory. Start mid-action.

HOOK VARIANTS (REQUIRED ÃÂ¢ÃÂÃÂ produce all 3 every time; pipeline rotates to prevent suppression):
  dramatic_peak    ÃÂ¢ÃÂÃÂ Opens with the most visually shocking beat of the story as a flat statement.
                     Example: "A whale swallowed him whole. He was still alive inside."
  impossible_odds  ÃÂ¢ÃÂÃÂ Opens with scale or numbers that make the situation feel hopeless.
                     Example: "One boy. One stone. One giant the size of a house."
  direct_question  ÃÂ¢ÃÂÃÂ A second-person question that puts the viewer inside the scene.
                     Example: "What would you do if you were thrown into a furnace alive?"

IMAGE PROMPT RULES (critical ÃÂ¢ÃÂÃÂ vague prompts produce identical AI images across videos):
- Every image_prompt MUST contain: (1) specific character name, (2) exact action they are
  doing RIGHT NOW in this scene, (3) specific location or environmental detail.
- BAD: "biblical figure in a landscape" ÃÂ¢ÃÂÃÂ generic, produces same image every time.
- BAD: "colorful scene from the Bible" ÃÂ¢ÃÂÃÂ completely generic.
- GOOD: "Jonah tumbling headfirst into the open jaws of a massive dark whale, ocean spray everywhere, stormy sky"
- GOOD: "Three boys ÃÂ¢ÃÂÃÂ Shadrach, Meshach, Abednego ÃÂ¢ÃÂÃÂ standing unharmed inside a roaring orange furnace, flames all around, calm expressions"
- GOOD: "Young David releasing a stone from his leather sling aimed at the towering giant Goliath in a rocky canyon"
- Scene 1 image_prompt: the single most dramatic PEAK visual ÃÂ¢ÃÂÃÂ the moment that stops scrolling.

THUMBNAIL SPEC (REQUIRED ÃÂ¢ÃÂÃÂ every video must include this; missing = invalid output):
Add a "thumbnail_spec" object to your JSON output:
{
  "thumbnail_spec": {
    "focal_subject": "One sentence: the single focal image at center of frame ÃÂ¢ÃÂÃÂ the peak action/animal/moment (e.g., 'Jonah falling headfirst into the open mouth of a massive dark whale against a stormy sky')",
    "overlay_words": "2ÃÂ¢ÃÂÃÂ4 ALL-CAPS words maximum ÃÂ¢ÃÂÃÂ kid-legible at phone size with thick outline (e.g., 'SWALLOWED ALIVE' or 'GIANT FALLS' or 'WALLS COME DOWN')",
    "character_emotion": "One word: the dominant emotion on the main character's face (e.g., 'terror', 'awe', 'defiance', 'shock', 'wonder', 'joy')"
  }
}
Do not omit thumbnail_spec. A script without it is incomplete and will be rejected.

CLIFFHANGER RULE — MADE FOR KIDS (deployed Jun 28 2026):
- End the Short on the MOST DRAMATIC UNRESOLVED MOMENT. Do NOT show God's full rescue.
- Scene 8 (final) must leave children wide-eyed at the impossible situation — not wrapping up the story.
- BAD final scene: "And so the three boys stepped out of the furnace safe and unharmed, and everyone praised God."
- GOOD final scene: "The fire was so hot it burned the guards outside the door. But inside the furnace... something no one could explain was happening."
- The Short makes kids NEED to watch the full Bible story for the resolution. Never write a complete ending.
- Never use "and they lived happily ever after" or any full resolution. End at the turning point, not after it.
"""

    # Per-channel narration length (W1-C Jul 12 2026): BSG's Jenny voice narrates
    # kids stories at ~2.4 w/s vs TMF's ~3.3 w/s -- same 42-55s target needs fewer words.
    if channel == "bsg":
        _wc_lo, _wc_hi, _tts_rate = 100, 130, 2.4
        _sc_lo, _sc_hi = 12, 17
    else:
        _wc_lo, _wc_hi, _tts_rate = 140, 180, 3.3
        _sc_lo, _sc_hi = 20, 32

    system_prompt = f"""You are a short-form video script writer for YouTube Shorts.

TARGET LENGTH: 42ÃÂ¢ÃÂÃÂ55 seconds. NEVER under 40 or over 60 seconds.
- Total narration across ALL scenes combined: {_wc_lo}ÃÂ¢ÃÂÃÂ{_wc_hi} words. Do not go below {_wc_lo} or above {_wc_hi}.
- TTS speaks at ~{_tts_rate} words/sec. {_wc_lo}w = ~42s, {_wc_hi}w = ~55s. Hit this range every time.
- Jun 7 2026 data: top-7 TMF videos (462ÃÂ¢ÃÂÃÂ802 views) all landed 42ÃÂ¢ÃÂÃÂ55s. Keep scripts tight.

Channel style: {style_guide}
{channel_rules}
Output ONLY valid JSON in this exact format:
{{
  "title": "Title following TITLE RULES above",
  "hook_variants": {{
    "shocking_claim":            "<Scene 1 narration, shocking_claim style, 10ÃÂ¢ÃÂÃÂ18 words>",
    "uncomfortable_question":    "<Scene 1 narration, uncomfortable_question style, 10ÃÂ¢ÃÂÃÂ18 words>",
    "behavioral_contradiction":  "<Scene 1 narration, behavioral_contradiction style, 10ÃÂ¢ÃÂÃÂ18 words>"
  }},
  "scenes": [
    {{
      "narration": "Spoken narration, {_sc_lo}ÃÂ¢ÃÂÃÂ{_sc_hi} words, sentences averaging 10ÃÂ¢ÃÂÃÂ14 words.",
      "image_prompt": "Vivid scene description for AI image generation. Be specific."
    }}
  ]
}}

Structural rules:
- Exactly {num_scenes} scenes
- SCENE 1 follows HOOK RULES above ÃÂ¢ÃÂÃÂ shortest scene, highest tension
- Each image_prompt: specific, visual, cinematic ÃÂ¢ÃÂÃÂ NOT abstract.
- No markdown, no explanation, ONLY the JSON object

PROSE QUALITY ÃÂ¢ÃÂÃÂ NO AI TELLS (applies to every narration field):
- No adverbs. Cut "deeply," "truly," "completely," "suddenly," "ultimately," "essentially," "clearly."
- Active voice only. Every sentence needs a human subject doing something. Not: "The behavior is driven by fear." ÃÂ¢ÃÂÃÂ "Fear drives the behavior."
- No inanimate subjects performing human actions. Not: "The pattern emerges from childhood." ÃÂ¢ÃÂÃÂ "Children learn this pattern early."
- No em-dashes anywhere in narration.
- No throat-clearing openers: "What this means is," "Here's the thing," "It's worth noting," "In other words," "Make no mistake," "The truth is."
- Two items beat three. Cut the third item from every list.
- Vary sentence rhythm. Never three consecutive sentences of matching length."""

    try:
        import openai
        # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Model backend: DeepSeek V3 primary (95% cheaper), GPT-4o fallback ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        openai_client = openai.OpenAI(api_key=api_key)   # always available as fallback
        if deepseek_key:
            client = openai.OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
            model_name = "deepseek-v4-flash"
            _fallback_available = True
            print(f"    Connecting to DeepSeek API (deepseek-v4-flash)...")
        else:
            client = openai_client
            model_name = "gpt-4o"
            _fallback_available = False
            print(f"    Connecting to OpenAI API (gpt-4o)...")

        user_msg = f"Write a {num_scenes}-scene script about: {topic}"
        # Task 4 test exception (weekly review Jul 19 2026): for these 2 flagged
        # topics, force the exact pre-approved concept-name title instead of
        # letting the model apply the channel's normal "Why You" rule. See
        # TMF_CONCEPT_NAME_TEST_ENABLED above to revert with a single flag flip.
        if channel == "tmf" and TMF_CONCEPT_NAME_TEST_ENABLED and topic in TMF_CONCEPT_NAME_TEST_TITLES:
            user_msg += (
                f"\n\nTITLE OVERRIDE (pre-approved 1-week test, Task 4 Jul 19 2026): "
                f"use EXACTLY this title, verbatim, do NOT rewrite it to start with "
                f'"Why You": "{topic}"'
            )
        extra_constraints = ""  # accumulated feedback for retries
        last_script: dict | None = None
        last_title_reason = ""
        last_word_count = 0

        # Up to 3 attempts for both TMF and BSG ÃÂ¢ÃÂÃÂ title format is critical for both.
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            print(f"    Making script generation request (attempt {attempt}/{max_attempts})...")
            messages = [
                {"role": "system", "content": system_prompt + extra_constraints},
                {"role": "user", "content": user_msg},
            ]
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=2000,
                    temperature=0.8,
                )
            except Exception as api_err:
                if _fallback_available:
                    print(f"    ÃÂ¢ÃÂÃÂ ÃÂ¯ÃÂ¸ÃÂ  DeepSeek failed ({type(api_err).__name__}: {str(api_err)[:80]})")
                    print(f"    ÃÂ°ÃÂÃÂÃÂ Falling back to GPT-4o...")
                    client = openai_client
                    model_name = "gpt-4o"
                    _fallback_available = False
                    resp = client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        max_tokens=2000,
                        temperature=0.8,
                    )
                else:
                    raise
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            script = json.loads(raw.strip())
            last_script = script

            # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Channel-specific guardrails ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
            if channel == "tmf":
                title_ok, title_reason = title_passes_tmf_rules(script.get("title", ""))
                wc_ok, word_count = script_word_count_ok(script)
                dup = title_already_published(script.get("title", ""), channel)

                problems = []
                if not title_ok:
                    problems.append(f"TITLE FAIL: {title_reason}")
                    last_title_reason = title_reason
                if not wc_ok:
                    problems.append(
                        f"LENGTH FAIL: total narration is {word_count} words "
                        f"(must be 140ÃÂ¢ÃÂÃÂ180 words = 42ÃÂ¢ÃÂÃÂ55s at ~3.3 words/sec TTS rate)"
                    )
                    last_word_count = word_count
                if dup:
                    problems.append(
                        f'DUPLICATE FAIL: title "{script.get("title")}" already published ÃÂ¢ÃÂÃÂ pick a different angle.'
                    )

                if not problems:
                    print(f"    ÃÂ¢ÃÂÃÂ Script passed validators (title + {word_count}w + unique)")
                    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Hook rotation (suppression filter) ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
                    # YouTube 2026 penalises channels that repeat the same
                    # hook style every video. Rotate across the 3 variants so
                    # the channel never looks like a format-farm to the algo.
                    hook_variants = script.get("hook_variants", {})
                    HOOK_STYLES = [
                        "shocking_claim",
                        "uncomfortable_question",
                        "behavioral_contradiction",
                    ]
                    available_hooks = {
                        k: v for k, v in hook_variants.items()
                        if k in HOOK_STYLES and isinstance(v, str) and v.strip()
                    }
                    if available_hooks:
                        chosen_style = random.choice(list(available_hooks))
                        chosen_hook  = available_hooks[chosen_style].strip()
                        if script.get("scenes") and chosen_hook:
                            script["scenes"][0]["narration"] = chosen_hook
                            script["_hook_style_used"] = chosen_style
                            print(f"    ÃÂ°ÃÂÃÂÃÂ£ Hook style selected: {chosen_style}")
                    return script

                print(f"    ÃÂ¢ÃÂÃÂ ÃÂ¯ÃÂ¸ÃÂ  Validator problems on attempt {attempt}: {' | '.join(problems)}")
                extra_constraints = (
                    "\n\nIMPORTANT ÃÂ¢ÃÂÃÂ your previous draft was REJECTED for these reasons:\n- "
                    + "\n- ".join(problems)
                    + "\nFix ALL of them in this next draft. The title MUST start with \"Why You\" or \"Why Your\" "
                      "and describe an observable behavior the viewer recognizes in themselves. No colons. "
                      "Total narration MUST be 140ÃÂ¢ÃÂÃÂ180 words across all scenes combined. "
                      "TTS speaks at ~3.3 words/sec ÃÂ¢ÃÂÃÂ 140w = 42s, 180w = 55s. Keep scripts tight."
                )
            else:
                # BSG title validator ÃÂ¢ÃÂÃÂ enforce "X emoji" format
                title = (script.get("title") or "").strip()
                # Fixed Jul 19 2026: this check only verified the suffix was PRESENT,
                # not that the whole title fit YouTube's real 100-char limit. The
                # actual upload (video_app.py /youtube-upload) does title[:100],
                # which silently chops the required suffix off any title that
                # passed here but ran long -- confirmed root cause for 3 titles
                # that published without the required format despite this
                # validator (weekly review Jul 19 2026). Now also reject
                # anything over 100 chars so it never reaches upload.
                bsg_format_ok = (
                    "|" not in title
                    and 0 < len(title) <= 60
                )
                if not bsg_format_ok:
                    print(f"    ÃÂ¢ÃÂÃÂ ÃÂ¯ÃÂ¸ÃÂ  BSG title format FAIL on attempt {attempt}: \"{title}\"")
                    extra_constraints = (
                        f"\n\nIMPORTANT ÃÂ¢ÃÂÃÂ your previous draft was REJECTED. "
                        f"Title was: \"{title}\" ({len(title)} chars)\n"
                        f"The BSG title MUST follow this EXACT format AND fit in 60 "
                        f"characters total (YouTube's real limit -- longer titles get "
                        f"silently truncated at upload and lose the required suffix): "
                        f"[Story tension phrase] [single emoji], no channel name, no pipes\n"
                        f"Examples: \"Noah's Ark ÃÂ°ÃÂÃÂÃÂ\"\n"
                        f"          \"David vs Goliath ÃÂ¢ÃÂÃÂÃÂ¯ÃÂ¸ÃÂ\"\n"
                        f"Keep the story name SHORT (no subtitle/colon clause) so the "
                        f"full title plus the required suffix stays under 60 characters. "
                        f"Rewrite the title to match this format exactly. No exceptions."
                    )
                    continue

                print(f"    ÃÂ¢ÃÂÃÂ BSG title validator: {title}")

                # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ BSG action gate validator ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
                bsg_dup = title_already_published(title, channel) if bsg_format_ok else False
                if bsg_dup:
                    print(f"    [FAIL] BSG duplicate on attempt {attempt}: \"{title}\" -- story already published, pick a different Bible story or a clearly different angle.")
                    extra_constraints = (
                        "\n\nIMPORTANT -- your previous draft was REJECTED as a DUPLICATE. "
                        f"Title was: \"{title}\"\n"
                        "This story (or a very similarly-worded version of it) has already been "
                        "published on this channel. Pick a COMPLETELY DIFFERENT Bible story -- "
                        "not just a reworded title for the same story."
                    )
                    continue
                # -- BSG word-count gate (W1-C Jul 12 2026) ---------------------
                # BSG had no length enforcement; published Shorts ran 68-97s.
                # 2026 Shorts algo weights absolute watch time -- keep 45-55s.
                wc_ok_bsg, bsg_words = script_word_count_ok_bsg(script)
                if not wc_ok_bsg:
                    print(f"    [FAIL] BSG length on attempt {attempt}: {bsg_words} words (must be 100-130 = ~45-55s at ~2.4 w/s)")
                    extra_constraints = (
                        "\n\nIMPORTANT -- your previous draft was REJECTED: narration length. "
                        f"Total narration was {bsg_words} words. On this channel the voice speaks at "
                        "~2.4 words/sec, so total narration across ALL scenes combined MUST be "
                        "100-130 words (renders ~45-55 seconds). Shorten every scene; keep the drama."
                    )
                    continue
                print(f"    [OK] BSG length gate: {bsg_words} words")

                if not script.get("has_action_gate", True):
                    print(f"    ÃÂ¢ÃÂÃÂ ÃÂ¯ÃÂ¸ÃÂ  BSG action gate FAIL on attempt {attempt}: story lacks dramatic peak")
                    extra_constraints = (
                        "\n\nIMPORTANT ÃÂ¢ÃÂÃÂ your previous draft FAILED the action gate. "
                        "The story needs ALL FOUR: (1) named character in danger, "
                        "(2) specific dramatic moment, (3) physical divine intervention, "
                        "(4) a visible concrete outcome. "
                        "Reframe around the most dramatic moment in the story, or pick a more action-forward story."
                    )
                    continue
                print(f"    ÃÂ¢ÃÂÃÂ BSG action gate: passed")

                # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ BSG thumbnail spec validator ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
                thumb = script.get("thumbnail_spec", {})
                thumb_ok = (
                    isinstance(thumb, dict)
                    and bool((thumb.get("focal_subject") or "").strip())
                    and bool((thumb.get("overlay_words") or "").strip())
                    and bool((thumb.get("character_emotion") or "").strip())
                )
                if not thumb_ok:
                    print(f"    ÃÂ¢ÃÂÃÂ ÃÂ¯ÃÂ¸ÃÂ  BSG thumbnail_spec missing/incomplete on attempt {attempt}")
                    extra_constraints = (
                        "\n\nIMPORTANT ÃÂ¢ÃÂÃÂ your previous draft was REJECTED: missing thumbnail_spec. "
                        "You MUST include a 'thumbnail_spec' object with three fields: "
                        "focal_subject (one sentence describing the peak action/image), "
                        "overlay_words (2ÃÂ¢ÃÂÃÂ4 ALL-CAPS words only), and "
                        "character_emotion (one word). Do not omit it."
                    )
                    continue
                print(f"    ÃÂ¢ÃÂÃÂ BSG thumbnail_spec: '{thumb.get('overlay_words')}' / {thumb.get('character_emotion')}")

                return script

        # All retries exhausted: intentionally skip this post rather than publish a bad title.
        # This is EXPECTED behavior, not a code error ÃÂ¢ÃÂÃÂ exit 0 so GH Actions shows green.
        raise ValueError(
            f"TITLE_VALIDATION_SKIP: All {max_attempts} attempts failed ÃÂ¢ÃÂÃÂ "
            f"last title: \"{(last_script or {}).get('title', 'n/a')}\" | "
            f"reason: {last_title_reason or 'format mismatch'}"
        )

    except json.JSONDecodeError as e:
        raise ValueError(f"OpenAI returned invalid JSON: {str(e)[:100]}")
    except ConnectionError as e:
        raise RuntimeError(f"Network error connecting to OpenAI: {str(e)[:120]}")
    except Exception as e:
        error_type = type(e).__name__
        raise RuntimeError(f"Script generation failed ({error_type}): {str(e)[:150]}")


def append_to_google_sheets(channel: str, title: str, url: str, status: str = "Success") -> None:
    """Append posted video to Google Sheets Auto-Post Log (GitHub Actions only)."""
    # Only run in GitHub Actions environment
    if not os.getenv("GITHUB_ACTIONS"):
        return

    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        print("ÃÂ¢ÃÂÃÂ ÃÂ¯ÃÂ¸ÃÂ  Google API libraries not available for Sheets logging")
        return

    try:
        # Load service account credentials from GitHub secret
        creds_json = os.getenv("GOOGLE_SHEETS_KEY")
        if not creds_json:
            print("  ÃÂ¢ÃÂÃÂ GOOGLE_SHEETS_KEY secret is EMPTY or not set in GitHub")
            return

        print(f"  ÃÂ¢ÃÂÃÂ GOOGLE_SHEETS_KEY found ({len(creds_json)} chars)")
        creds_dict = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )

        # Build Sheets API client
        service = build("sheets", "v4", credentials=creds)
        spreadsheet_id = "1JKlBnYdv-_r3FcjozBtpRxLNRiAoA1ezLRz2W-7vVWI"
        sheet_name = "Auto-Post Log"

        # Prepare row data
        channel_label = CHANNEL_LABELS.get(channel, channel)
        # Central Time (auto-handles CDT/CST switch twice a year)
        timestamp = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M:%S")

        row = [timestamp, channel_label, title, status, url, ""]

        # Append to sheet
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:G",
            valueInputOption="USER_ENTERED",
            body={"values": [row]}
        ).execute()

        print(f"  ÃÂ°ÃÂÃÂÃÂ Logged to Google Sheets: {channel_label} ÃÂ¢ÃÂÃÂ {title}")

    except Exception as e:
        # Log error but don't break the workflow
        import traceback
        error_msg = f"Sheets logging failed: {str(e)[:100]}"
        print(f"  ÃÂ¢ÃÂÃÂ ÃÂ¯ÃÂ¸ÃÂ  {error_msg}")
        # Still save locally for debugging
        print(f"     (Video posted but not logged to Sheets. Check logs.)")


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Dependency Management ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

def ensure_dependencies() -> bool:
    """Install missing Python packages needed for video_app.py. Returns True if ready."""
    needed = []
    try:
        import flask  # noqa: F401
    except ImportError:
        needed.append("flask")
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        needed.append("edge-tts")
    try:
        import openai  # noqa: F401
    except ImportError:
        needed.append("openai")
    try:
        import googleapiclient  # noqa: F401
    except ImportError:
        needed.extend(["google-api-python-client", "google-auth-httplib2", "google-auth-oauthlib"])

    if not needed:
        return True

    print(f"  ÃÂ°ÃÂÃÂÃÂ¦ Installing missing packages: {', '.join(needed)}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "--break-system-packages"] + needed,
            capture_output=True, timeout=120
        )
        if result.returncode != 0:
            # Try without --break-system-packages (older pip)
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet"] + needed,
                capture_output=True, timeout=120
            )
        if result.returncode == 0:
            print(f"  ÃÂ¢ÃÂÃÂ Packages installed successfully.")
            return True
        else:
            err = result.stderr.decode("utf-8", errors="replace")[:200]
            print(f"  ÃÂ¢ÃÂÃÂ ÃÂ¯ÃÂ¸ÃÂ pip install failed: {err}")
            return False
    except Exception as e:
        print(f"  ÃÂ¢ÃÂÃÂ ÃÂ¯ÃÂ¸ÃÂ Could not install packages: {e}")
        return False


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Server Management ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

SERVER_URL = "http://localhost:5002"


def server_running() -> bool:
    try:
        urllib.request.urlopen(SERVER_URL, timeout=2)
        return True
    except Exception:
        return False


def wait_for_server(timeout: int = 60) -> bool:
    print("  ÃÂ¢ÃÂÃÂ³ Waiting for server to start...")
    for _ in range(timeout):
        if server_running():
            print("  ÃÂ¢ÃÂÃÂ Server ready!")
            return True
        time.sleep(1)
    return False


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ API Helpers ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

def api_post(path: str, data: dict, timeout: int = 600) -> dict:
    url     = f"{SERVER_URL}{path}"
    payload = json.dumps(data).encode()
    req     = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        # Show the actual error response from Flask
        error_body = e.read().decode()
        # Aug 25 2026: the raise used to sit INSIDE this try with a bare `except:`
        # after it, so it caught its own RuntimeError and re-raised the generic
        # form. That destroyed the "TITLE_VALIDATION_SKIP" prefix the caller
        # matches on, turning an intentional skip into a red exit-1 run.
        try:
            detail = json.loads(error_body).get("error", error_body)
        except (ValueError, TypeError, AttributeError):
            detail = f"(HTTP {e.code}) {error_body[:200]}"
        raise RuntimeError(f"Flask error: {detail}")


def api_get(path: str, timeout: int = 30) -> dict:
    url = f"{SERVER_URL}{path}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ YouTube Metadata ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

def build_yt_metadata(channel: str, title: str, topic: str = "", longform_url: str = "") -> dict:
    """Build YouTube description + tags for a channel.

    Description is keyword-rich for Shorts search discoverability (Jan 2026 Shorts
    search filter update means descriptions now drive meaningful traffic). Topic string
    is embedded so each video gets unique, searchable copy rather than boilerplate.
    """
    # Extract the core subject and angle from topic.
    # Topics are formatted as "Subject - Angle" or just "Subject"
    sep = " - "
    topic_subject = topic.split(sep)[0].strip() if sep in topic else topic.strip()
    topic_angle   = topic.split(sep, 1)[1].strip() if sep in topic else ""

    if channel == "bsg":
        longform_prefix = f"📖 Watch the full story: {longform_url}\n\n" if longform_url else ""
        if topic_subject:
            description = (
                longform_prefix +
                f"📖 {title}\n\n"
                f"{topic_subject} - {topic_angle + ' ' if topic_angle else ''}"
                f"Bible Stories for Kids, brought to you by Bible Story Garden. "
                f"Faith-filled, family-friendly shorts that bring Scripture to life. "
                f"Perfect for Christian families, Sunday school, and kids who love God's Word.\n\n"
                "#BibleStories #KidsFaith #BibleForKids #ChristianKids #YouTubeShorts"
            )
        else:
            description = (
                longform_prefix +
                f"📖 {title}\n\n"
                "Bible Stories for Kids - brought to you by Bible Story Garden! "
                "Faith-filled, family-friendly shorts that bring Scripture to life.\n\n"
                "#BibleStories #KidsFaith #BibleForKids #ChristianKids #YouTubeShorts"
            )
        tags = "Bible,Bible Stories,Kids,Faith,Jesus,God,Christian,Children,YouTube Shorts,Bible for Kids"
        if topic_subject:
            topic_words = [w for w in topic_subject.replace("'", "").split() if len(w) > 3]
            tags += "," + ",".join(topic_words[:5])
    elif channel == "mz":
        longform_prefix_mz = f"⚡ Watch the full story: {longform_url}\n\n" if longform_url else ""
        if topic_subject:
            description = (
                longform_prefix_mz +
                f"⚡ {title}\n\n"
                f"{topic_subject}"
                f"{' - ' + topic_angle if topic_angle else ''}. "
                f"Business collapses, corporate scandals, and the moments that changed history - "
                f"brought to you by Minute Zero. "
                f"Every video is one decision, one moment, one company that changed forever.\n\n"
                "#BusinessHistory #CorporateScandal #MinuteZero #BusinessFails #YouTubeShorts"
            )
        else:
            description = (
                longform_prefix_mz +
                f"⚡ {title}\n\n"
                "Business collapses and corporate scandals - brought to you by Minute Zero. "
                "One moment. One company. Everything changes.\n\n"
                "#BusinessHistory #CorporateScandal #MinuteZero #BusinessFails #YouTubeShorts"
            )
        tags = "business history,corporate scandal,business failure,company collapse,Minute Zero,YouTube Shorts,finance,Wall Street"
        if topic_subject:
            topic_words = [w for w in topic_subject.replace("'", "").split() if len(w) > 3]
            tags += "," + ",".join(topic_words[:5])
    else:
        # TMF
        longform_prefix_tmf = f"🧠 Watch the full deep-dive: {longform_url}\n\n" if longform_url else ""
        if topic_subject:
            description = (
                longform_prefix_tmf +
                f"🧠 {title}\n\n"
                f"{topic_subject}"
                f"{' - ' + topic_angle if topic_angle else ''}. "
                f"Dark psychology and human behavior explained - brought to you by The Mind Files. "
                f"Why do people do what they do? Explore the science behind manipulation, "
                f"personality, and the hidden forces shaping every decision.\n\n"
                "#Psychology #DarkPsychology #HumanBehavior #MindFiles #YouTubeShorts"
            )
        else:
            description = (
                longform_prefix_tmf +
                f"🧠 {title}\n\n"
                "Dark psychology and human behavior explained - brought to you by The Mind Files. "
                "Why humans do what they do.\n\n"
                "#Psychology #DarkPsychology #HumanBehavior #MindFiles #YouTubeShorts"
            )
        tags = "psychology,dark psychology,human behavior,mind,mental health,behavioral science,YouTube Shorts,The Mind Files"
        if topic_subject:
            topic_words = [w for w in topic_subject.replace("'", "").split() if len(w) > 3]
            tags += "," + ",".join(topic_words[:5])

    return {"description": description, "tags": tags}


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Trigger File Support ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

def write_trigger_file(channel: str, topic: str, script: dict) -> Path:
    """Write a trigger file so auto_watcher.sh can run the pipeline on Mac."""
    ts       = time.strftime("%Y%m%d_%H%M")
    filename = BASE_DIR / f"auto_trigger_{channel}_{ts}.json"
    payload  = {
        "channel":      channel,
        "topic":        topic,
        "script":       script,
        "scheduled_at": time.strftime("%Y-%m-%d %H:%M"),
        "status":       "pending",
    }
    filename.write_text(json.dumps(payload, indent=2))
    return filename


def load_trigger_file(path: str) -> dict:
    """Load a trigger file written by the scheduled task."""
    return json.loads(Path(path).read_text())


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Run Pipeline via Server ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

def run_headless(channel: str, topic: str, script: dict) -> str:
    """Generate and upload video directly without Flask server (CI mode)."""
    label  = CHANNEL_LABELS[channel]
    voice  = CHANNEL_VOICES[channel]
    title  = script["title"]
    scenes = script["scenes"]

    print(f"  Title : {title}")
    print(f"  Scenes: {len(scenes)}")

    # Import video generation from video_app.py directly
    try:
        from video_app import run_video_job
        import urllib.request
    except ImportError as e:
        print(f"ÃÂ¢ÃÂÃÂ Could not import video generation: {e}")
        sys.exit(1)

    print(f"\nÃÂ°ÃÂÃÂÃÂ¬ Creating video...")
    try:
        # Run video job directly (no Flask server needed)
        video_path = run_video_job(
            title=title,
            scenes=scenes,
            voice=voice,
            fmt="vertical",
            channel=channel
        )
        print(f"  ÃÂ¢ÃÂÃÂ Video created: {Path(video_path).name}")
    except Exception as e:
        print(f"ÃÂ¢ÃÂÃÂ Video generation failed: {e}")
        sys.exit(1)

    print(f"\nÃÂ°ÃÂÃÂÃÂ¤ Uploading to YouTube ({label})...")
    longform_url = get_longform_url(channel)
    yt_meta = build_yt_metadata(channel, title, topic=topic, longform_url=longform_url)
    try:
        # Use the Flask server's upload endpoint via direct import
        from video_app import youtube_upload as yt_upload_func
        upload_result = yt_upload_func(
            channel=channel,
            video_path=str(Path(video_path).name),
            title=title,
            description=yt_meta["description"],
            tags=yt_meta["tags"],
            privacy="public"
        )
        yt_url = upload_result.get("url", f"https://youtube.com/@{channel}")
        print(f"  ÃÂ¢ÃÂÃÂ Uploaded: {yt_url}")
        return yt_url
    except Exception as e:
        print(f"ÃÂ¢ÃÂÃÂ Upload failed: {e}")
        sys.exit(1)


def run_via_server(channel: str, topic: str, script: dict) -> str:
    """Send pre-generated script to the running video server. Returns video URL."""
    label  = CHANNEL_LABELS[channel]
    voice  = CHANNEL_VOICES[channel]
    title  = script["title"]
    scenes = script["scenes"]

    print(f"  Title : {title}")
    print(f"  Scenes: {len(scenes)}")

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Step: Create video ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    print(f"\nÃÂ°ÃÂÃÂÃÂ¬ Creating video...")
    try:
        gen_resp = api_post("/generate", {
            "title":   title,
            "scenes":  scenes,
            "voice":   voice,
            "format":  "vertical",
            "channel": channel,
        }, timeout=10)
    except Exception as e:
        print(f"ÃÂ¢ÃÂÃÂ Video generation request failed: {e}")
        sys.exit(1)

    if "error" in gen_resp:
        print(f"ÃÂ¢ÃÂÃÂ Video start error: {gen_resp['error']}")
        sys.exit(1)

    # Poll until video is done (can take 3-10 minutes)
    print("  ⏳ Processing video (this takes a few minutes)...")
    deadline = time.time() + 1200  # 20 min max — leaves room for YT upload within 90-min GH Actions timeout
    while time.time() < deadline:
        time.sleep(5)
        try:
            status = api_get("/job-status")
        except Exception:
            time.sleep(5)
            continue
        if not status.get("running"):
            break
        elapsed = int(time.time() - (deadline - 900))
        if elapsed % 30 == 0:
            print(f"  ... still working ({elapsed}s)")

    try:
        status = api_get("/job-status")
    except Exception as e:
        print(f"ÃÂ¢ÃÂÃÂ Could not get final job status: {e}")
        sys.exit(1)

    if status.get("error"):
        print(f"ÃÂ¢ÃÂÃÂ Video generation error: {status['error']}")
        # Print video_server.log tail for debugging
        log_path = BASE_DIR / "video_server.log"
        if log_path.exists():
            print("\nÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ video_server.log (last 40 lines) ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ")
            lines = log_path.read_text(errors="replace").splitlines()
            print("\n".join(lines[-40:]))
        sys.exit(1)

    video_path = status.get("output", "")
    if not video_path:
        print("ÃÂ¢ÃÂÃÂ No output video reported.")
        # Print video_server.log tail so we can see what failed
        log_path = BASE_DIR / "video_server.log"
        if log_path.exists():
            print("\nÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ video_server.log (last 40 lines) ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ")
            lines = log_path.read_text(errors="replace").splitlines()
            print("\n".join(lines[-40:]))
        sys.exit(1)

    filename = Path(video_path).name

    # ---- Caption verification (added Aug 24 2026) ----------------------
    # video_app.py logged caption status only to video_server.log, which never
    # reaches the Actions output. That is why TMF + BSG shipped ~100 days of
    # Shorts with no captions and nothing flagged it. Surface it here.
    _cap = status.get("captions") or {}
    if _cap:
        _ok   = _cap.get("captioned_scenes", 0)
        _tot  = _cap.get("total_scenes", 0)
        _fail = _cap.get("render_failures", 0)
        print(f"  [CAPTIONS] {_ok}/{_tot} scenes captioned, {_fail} render failure(s)")
        if _tot and _ok < _tot:
            print(f"::error::CAPTIONS DEGRADED -- only {_ok} of {_tot} scenes had word timings")
            print("   Refusing to upload a caption-less Short. This is the May-Aug 2026 outage.")
            sys.exit(1)
        if _fail:
            print(f"::warning::CAPTION RENDER FAILED on {_fail} clip(s) -- libass fell back to no captions")
    else:
        print("  [CAPTIONS] status unavailable from video server")

    # ---- Pre-upload QC gate (added Aug 23 2026) -------------------------
    # Blocks unambiguously broken renders (silent audio, A/V drift, dead
    # final frame, truncated file). Odd-but-plausible files only warn.
    # See render_qc.py for the failures that motivated this.
    try:
        from render_qc import enforce as _qc_enforce, QCError as _QCError
    except ImportError as _qc_imp_err:
        print(f"::error::QC gate unavailable ({_qc_imp_err}) -- refusing to upload unchecked.")
        print("   Set QC_DISABLE=1 to bypass deliberately.")
        sys.exit(1)
    else:
        try:
            _qc_enforce(video_path, channel=channel, kind="short")
        except _QCError as _qc_err:
            print(f"\n{_qc_err}")
            print("   Not uploading. Re-render and try again.")
            sys.exit(1)

    print(f"  ÃÂ¢ÃÂÃÂ Video ready: {filename}")

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Step: Upload to YouTube ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    longform_url = get_longform_url(channel)
    yt_meta = build_yt_metadata(channel, title, topic=topic, longform_url=longform_url)
    print(f"\nÃÂ°ÃÂÃÂÃÂ¤ Uploading to YouTube ({label})...")
    try:
        upload_resp = api_post("/youtube-upload", {
            "channel":     channel,
            "video_path":  filename,
            "title":       title,
            "description": yt_meta["description"],
            "tags":        yt_meta["tags"],
            "privacy":     "public",
        }, timeout=600)
    except Exception as e:
        print(f"ÃÂ¢ÃÂÃÂ Upload request failed: {e}")
        sys.exit(1)

    if "error" in upload_resp:
        print(f"ÃÂ¢ÃÂÃÂ Upload error: {upload_resp['error']}")
        sys.exit(1)

    video_url = upload_resp.get("url", "(unknown)")
    video_id  = upload_resp.get("video_id", "")
    return video_url, video_id


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Main ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ



# ── Short→Longform funnel helpers ─────────────────────────────────────────────

def get_longform_url(channel: str) -> str:
    """Return the best longform destination URL for a channel.

    Priority: env-var playlist ID (TMF) → hardcoded playlist → channel page.
    These are the full-episode playlists where viewers can binge all long-form content.
    """
    if channel == "tmf":
        playlist_id = os.getenv("TMF_LONGFORM_PLAYLIST_ID", "").strip()
        if playlist_id:
            return f"https://www.youtube.com/playlist?list={playlist_id}"
        return "https://www.youtube.com/@TheMindFiles/videos"
    elif channel == "bsg":
        return "https://www.youtube.com/playlist?list=PLWwJ5gjyjteowfCIsBJ-9UuoMd-12I3Jg"
    else:  # mz
        return "https://www.youtube.com/playlist?list=PLFxFhPJANicOqF4b_CsQxFoIh5AZlcsIJ"


def post_funnel_comment(channel: str, video_id: str, longform_url: str) -> None:
    """Post a Short→Longform funnel comment as channel owner immediately after upload.

    Non-fatal — a comment failure never blocks the upload.
    Note: YouTube Data API v3 has no public pin endpoint; the comment is posted
    immediately after upload so it is the first (top) comment on the video.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build as yt_build

        token_file = BASE_DIR / f"youtube_token_{channel}.json"
        if not token_file.exists():
            print(f"  ⚠️  Funnel comment skipped: token file missing for {channel}")
            return

        creds = Credentials.from_authorized_user_file(
            str(token_file),
            ["https://www.googleapis.com/auth/youtube.upload",
             "https://www.googleapis.com/auth/youtube",
             "https://www.googleapis.com/auth/youtube.force-ssl"]  # required for commentThreads().insert()
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json())

        youtube = yt_build("youtube", "v3", credentials=creds)

        if channel == "tmf":
            comment_text = (
                f"🧠 Want the FULL breakdown?\n"
                f"👉 {longform_url}\n\n"
                f"New psychology deep-dives every week — subscribe so you never miss the next one. 🔔"
            )
        elif channel == "bsg":
            comment_text = (
                f"📖 Want to hear the FULL story?\n"
                f"👉 {longform_url}\n\n"
                f"New Bible stories for kids every week — subscribe and share with your family! 🙏"
            )
        else:  # mz
            comment_text = (
                f"⚡ Want the FULL story? Every minute mattered.\n"
                f"👉 {longform_url}\n\n"
                f"New company collapses every week — subscribe so you don't miss the next one. 📈"
            )

        thread = youtube.commentThreads().insert(
            part="snippet",
            body={"snippet": {
                "videoId": video_id,
                "topLevelComment": {"snippet": {"textOriginal": comment_text}}
            }}
        ).execute()
        comment_id = thread.get("id", "?")
        print(f"  💬 Funnel comment posted ({channel}): {comment_id[:24]}...")
    except Exception as e:
        print(f"  ⚠️  Funnel comment failed (non-fatal): {str(e)[:200]}")


def post_tmf_channel_comment(youtube, video_id: str) -> None:
    """Post affiliate/lead-magnet comment as TMF channel owner on every Short."""
    _AMZN_TAG     = "themindf20-20"
    _AUDIBLE_LINK = f"https://www.amazon.com/hz/audible/mlp/membership/prime?tag={_AMZN_TAG}"
    _LEADMAGNET   = "https://midwestmade4u-prog.github.io/themindf-hub/"

    if "YOUR_FORM" in _LEADMAGNET or "PASTE" in _LEADMAGNET:
        comment_text = (
            f"Ã°ÂÂÂ The books behind this video are linked in the bio.\n"
            f"Ã°ÂÂÂ§ Free audiobook trial (Audible): {_AUDIBLE_LINK}\n"
            f"\nAs an Amazon Associate I earn from qualifying purchases."
        )
    else:
        comment_text = (
            f"Ã°ÂÂÂ Free guide Ã¢ÂÂ 7 Dark Psychology Tactics: {_LEADMAGNET}\n"
            f"Ã°ÂÂÂ§ Free audiobook trial (Audible): {_AUDIBLE_LINK}\n"
            f"Ã°ÂÂÂ Full book list in bio.\n"
            f"\nAs an Amazon Associate I earn from qualifying purchases."
        )
    try:
        youtube.commentThreads().insert(
            part="snippet",
            body={"snippet": {"videoId": video_id, "topLevelComment": {"snippet": {"textOriginal": comment_text}}}}
        ).execute()
        print(f"  Ã°ÂÂÂ¬ Affiliate comment posted on {video_id}")
    except Exception as e:
        print(f"  Ã¢ÂÂ Ã¯Â¸Â Comment post failed (non-fatal): {e}")

def post_channel_affiliate_comment(channel: str, video_id: str) -> None:
    """Post an affiliate pinned comment for TMF or BSG Shorts. Pin manually in Studio.

    Self-contained: builds its own YouTube client from the per-channel token file.
    Non-fatal — silently no-ops on MFK reclassification or any API error.
    """
    _TAG_MAP = {
        "tmf": "themindf20-20",
        "bsg": "biblestory07-20",
    }
    tag = _TAG_MAP.get(channel)
    if not tag:
        return  # MZ uses a separate file; skip unknown channels

    audible_url = f"https://www.amazon.com/audible/mt/audiblemember?tag={tag}"

    if channel == "tmf":
        _leadmagnet = "https://midwestmade4u-prog.github.io/themindf-hub/"
        comment_text = (
            f"\U0001f4c4 Free guide — 7 Dark Psychology Tactics: {_leadmagnet}\n"
            f"\U0001f3a7 Free audiobook trial (Audible): {audible_url}\n"
            f"\U0001f4da Full book list in bio.\n\n"
            "As an Amazon Associate I earn from qualifying purchases."
        )
    else:  # bsg
        comment_text = (
            f"\U0001f4da Looking for illustrated Bibles and faith-based books for your family? "
            f"Check the description — and try Audible free: {audible_url}\n\n"
            "As an Amazon Associate I earn from qualifying purchases."
        )

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build as yt_build

        token_file = BASE_DIR / f"youtube_token_{channel}.json"
        if not token_file.exists():
            print(f"  ⚠️  Affiliate comment skipped: token file missing for {channel}")
            return

        creds = Credentials.from_authorized_user_file(
            str(token_file),
            ["https://www.googleapis.com/auth/youtube.upload",
             "https://www.googleapis.com/auth/youtube",
             "https://www.googleapis.com/auth/youtube.force-ssl"]  # required for commentThreads().insert()
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json())

        youtube = yt_build("youtube", "v3", credentials=creds)
        youtube.commentThreads().insert(
            part="snippet",
            body={"snippet": {"videoId": video_id,
                              "topLevelComment": {"snippet": {"textOriginal": comment_text}}}}
        ).execute()
        print(f"  ✅ Affiliate comment posted ({channel}) — pin it in Studio!")
    except Exception as e:
        print(f"  ⚠️  Affiliate comment failed (non-fatal): {str(e)[:200]}")


def main():
    parser = argparse.ArgumentParser(description="Auto-create and post a YouTube Short")
    parser.add_argument("--channel", choices=["bsg", "tmf"],
                        help="Which channel to post to: bsg or tmf")
    parser.add_argument("--trigger-file",
                        help="Path to a trigger JSON file (written by scheduled task)")
    args = parser.parse_args()

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Determine mode ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    if args.trigger_file:
        # Trigger-file mode: script was pre-generated by the scheduled task
        trigger = load_trigger_file(args.trigger_file)
        channel = trigger["channel"]
        topic   = trigger["topic"]
        script  = trigger["script"]
        print(f"\n{'ÃÂ¢ÃÂÃÂ' * 60}")
        print(f"  ÃÂ°ÃÂÃÂÃÂ¬ Auto-Post (trigger)  |  {CHANNEL_LABELS[channel]}  |  {time.strftime('%Y-%m-%d %H:%M')}")
        print(f"{'ÃÂ¢ÃÂÃÂ' * 60}")
        print(f"\nÃÂ°ÃÂÃÂÃÂ Topic: {topic}  (from scheduled task at {trigger.get('scheduled_at', '?')})")
    else:
        # Standard mode: pick topic and generate script via server
        if not args.channel:
            parser.error("--channel is required unless --trigger-file is provided")
        channel = args.channel
        topic   = None
        script  = None

    label = CHANNEL_LABELS[channel]
    voice = CHANNEL_VOICES[channel]

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Burst-publishing guard ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    # Stop manual re-runs / workflow_dispatch from stacking >cap videos in a day.
    if not os.getenv("BURST_GUARD_OVERRIDE"):
        burst_guard_or_exit(channel)

    if not args.trigger_file:
        print(f"\n{'ÃÂ¢ÃÂÃÂ' * 60}")
        print(f"  ÃÂ°ÃÂÃÂÃÂ¬ Auto-Post  |  {label}  |  {time.strftime('%Y-%m-%d %H:%M')}")
        print(f"{'ÃÂ¢ÃÂÃÂ' * 60}")
        try:
            topic = pick_topic(channel)
        except TopicBankExhausted as te:
            # Clean skip, exit 0 -- green in Actions. Same convention as the
            # title-validation skip above: a bad post is worse than no post.
            print(f"\n[SKIPPED] {te}")
            append_to_google_sheets(channel, f"[SKIPPED] {str(te)[:100]}", "",
                                    status="Skipped - Topic Bank Exhausted")
            sys.exit(0)
        print(f"\nÃÂ°ÃÂÃÂÃÂ Topic: {topic}")

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Ensure dependencies installed ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    print("\nÃÂ°ÃÂÃÂÃÂ Checking dependencies...")
    deps_ok = ensure_dependencies()
    if not deps_ok:
        print("  ÃÂ¢ÃÂÃÂ ÃÂ¯ÃÂ¸ÃÂ Could not install all dependencies (likely running in restricted environment).")
        if script:
            # We have a pre-generated script ÃÂ¢ÃÂÃÂ save trigger file for Mac watcher
            tf = write_trigger_file(channel, topic, script)
            print(f"\nÃÂ°ÃÂÃÂÃÂ Trigger file saved for Mac watcher: {tf.name}")
            print("   The Mac watcher (auto_watcher.sh) will pick this up and complete the post.")
        else:
            print("   Run this script manually on your Mac to complete the post.")
        sys.exit(0)

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Start server if needed ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    server_proc        = None
    server_was_running = server_running()

    if server_was_running:
        print("\nÃÂ°ÃÂÃÂÃÂ Video server already running ÃÂ¢ÃÂÃÂ using it.")
    else:
        print("\nÃÂ°ÃÂÃÂÃÂ Starting video server...")
        server_log = open(BASE_DIR / "video_server.log", "w")
        server_proc = subprocess.Popen(
            [sys.executable, str(BASE_DIR / "video_app.py")],
            stdout=server_log,
            stderr=server_log,
        )
        if not wait_for_server(timeout=90):
            print("ÃÂ¢ÃÂÃÂ Server failed to start within 90 seconds.")
            sys.exit(1)

    try:
        # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Generate or use pre-generated script ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
        if script is None:
            # Generate script via Flask server
            print(f"\nÃÂ¢ÃÂÃÂÃÂ¯ÃÂ¸ÃÂ  Generating 8-scene script  (voice: {voice})...")
            try:
                script_resp = api_post("/generate-script", {
                    "topic":      topic,
                    "channel":    channel,
                    "num_scenes": 8,
                })
                if "error" in script_resp:
                    raise ValueError(script_resp["error"])
                script = script_resp["script"]
            except (ValueError, RuntimeError) as e:
                # api_post raises RuntimeError, not ValueError -- this branch was
                # unreachable for every Flask error. And the marker is no longer a
                # prefix once api_post wraps it, so match anywhere.
                err = str(e)
                if "TITLE_VALIDATION_SKIP" in err:
                    # Intentional skip ÃÂ¢ÃÂÃÂ title validator rejected all 3 attempts.
                    # This is EXPECTED behavior, not a code error. Exit 0 (green in GH Actions).
                    print(f"\nÃÂ¢ÃÂÃÂ­ÃÂ¯ÃÂ¸ÃÂ  SKIPPED (title validation): {err}")
                    print("   No video posted this run. This is intentional ÃÂ¢ÃÂÃÂ a bad title is worse than no post.")
                    append_to_google_sheets(channel, f"[SKIPPED] {err[err.index('TITLE_VALIDATION_SKIP'):][:100]}", "", status="Skipped - Title Validation")
                    sys.exit(0)
                print(f"ÃÂ¢ÃÂÃÂ Script generation failed: {e}")
                sys.exit(1)
            except Exception as e:
                print(f"ÃÂ¢ÃÂÃÂ Script generation failed: {e}")
                sys.exit(1)

        title = script["title"]

        # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Run the pipeline ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
        print(f"\nÃÂ¢ÃÂÃÂÃÂ¯ÃÂ¸ÃÂ  Script ready: {title}")
        video_url, video_id = run_via_server(channel, topic, script)

        print(f"  ÃÂ¢ÃÂÃÂ Posted! {video_url}")

        # Short→Longform funnel comment (non-fatal)
        if video_id:
            post_funnel_comment(channel, video_id, get_longform_url(channel))
            # Affiliate comment (TMF + BSG only — MZ handled in auto_post_mz.py)
            if channel in ("tmf", "bsg"):
                post_channel_affiliate_comment(channel, video_id)

        # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Log success ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
        mark_posted(channel, topic, title, video_url)

        # Clean up trigger file if it was used
        if args.trigger_file:
            try:
                Path(args.trigger_file).unlink()
            except Exception:
                pass

        print(f"\n{'ÃÂ¢ÃÂÃÂ' * 60}")
        print(f"  ÃÂ°ÃÂÃÂÃÂ SUCCESS ÃÂ¢ÃÂÃÂ {label}")
        print(f"  Topic : {topic}")
        print(f"  Title : {title}")
        print(f"  URL   : {video_url}")
        print(f"{'ÃÂ¢ÃÂÃÂ' * 60}\n")

    finally:
        # Only stop the server if WE started it
        if server_proc and not server_was_running:
            print("  ÃÂ°ÃÂÃÂÃÂ Stopping video server...")
            server_proc.terminate()
            server_proc.wait(timeout=10)


if __name__ == "__main__":
    main()
