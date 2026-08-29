#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  auto_post_mz.py — Minute Zero auto-post orchestrator        ║
╚══════════════════════════════════════════════════════════════╝

Flow:
  1. Pick topic (based on weekday + time → Format A / B / C)
  2. Load v3 prompt from MZ_Channel/MZ_Script_Generator_Prompt_v3.md
  3. Call OpenAI (or Anthropic) API → get v3 JSON output
  4. video_mz.render_video() → produces master + platform variants + thumb
  5. Upload master to YouTube (via video_mz_upload helper)
  6. Log to auto_post_log.json + append to Google Sheets
  7. (Future) Push TikTok variant to Content Posting API

Usage:
  python3 auto_post_mz.py                   # pick topic automatically
  python3 auto_post_mz.py --format A        # force a specific format
  python3 auto_post_mz.py --topic "Knight Capital"
  python3 auto_post_mz.py --dry-run         # render only, no upload

Required env vars:
  OPENAI_API_KEY                — script generation (or ANTHROPIC_API_KEY, see MODEL_BACKEND below)
  PEXELS_API_KEY                — video clip sourcing
  (YouTube token is loaded from youtube_token_mz.json)

Required Python deps (installed in GH Action workflow):
  edge-tts, Pillow, requests, openai, google-api-python-client,
  google-auth, google-auth-httplib2, google-auth-oauthlib
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import json
import os
import random
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
LOG_FILE    = BASE_DIR / "auto_post_log.json"
# Per-channel log — MZ workflow commits only this file, no merge conflicts with TMF/BSG
MZ_LOG_FILE = BASE_DIR / "mz_post_log.json"
LONGFORM_QUEUE_FILE = BASE_DIR / "longform_queue.json"   # short→longform amplification queue
MZ_CHANNEL_DIR = BASE_DIR / "MZ_Channel"
MZ_PROMPT_V3 = MZ_CHANNEL_DIR / "MZ_Script_Generator_Prompt_v3.md"
MZ_OUTPUT_DIR = BASE_DIR / "MZ_Output"
MZ_OUTPUT_DIR.mkdir(exist_ok=True)

# ── Model backend ──────────────────────────────────────────────────────────
MODEL_BACKEND = os.environ.get("MZ_MODEL_BACKEND", "openai").lower()   # openai|anthropic
OPENAI_MODEL    = os.environ.get("MZ_OPENAI_MODEL",    "gpt-4o")
ANTHROPIC_MODEL = os.environ.get("MZ_ANTHROPIC_MODEL", "claude-sonnet-4-6")


# ─── Topic banks (mirror of MZ_Topic_Bank_v1.md as of Apr 24 2026) ──────────

ONE_BAD_DAY_TOPICS = [
    "Knight Capital — 12 minutes of bad code → $440M evaporated, Aug 1, 2012, 9:30 AM",
    "Coca-Cola — Apr 23, 1985 — the day they announced 'New Coke'",
    "Yahoo — 1998 meeting — Yahoo passes on buying Google for $1M",
    "Blockbuster — 2000 — the phone call rejecting Netflix for $50M",
    "Quaker Oats — 1994 — the Snapple acquisition decision ($1.7B → $300M in 27 months)",
    "JCPenney (Ron Johnson) — Feb 1, 2012 — killing all coupons on day one",
    "AOL–Time Warner — Jan 10, 2000 — merger announcement press conference",
    "Enron — Aug 14, 2001 — Skilling's sudden resignation call",
    "Theranos — Oct 16, 2015 — WSJ story drops",
    "FTX — Nov 2, 2022 — CoinDesk leaks the Alameda balance sheet",
    "Long-Term Capital Management — Aug 17, 1998 — Russia defaults",
    "Arthur Andersen — Oct 23, 2001 — the shredding-party memo",
    "Borders — 2001 — signing the deal to hand their website to Amazon",
    "Wells Fargo — The 2011 sales mandate memo ('eight is great')",
    "Boeing — The MCAS single-sensor design call (737 MAX)",
    "MySpace — Jul 19, 2005 — News Corp pays $580M and hands it to people who saw it as a billboard, not a platform",
    "Bear Stearns — Mar 13, 2008 — the midnight call admitting insolvency",
    "Lehman Brothers — Sep 14, 2008 — the weekend Paulson refused to bail them out",
    "MF Global — Oct 2011 — Jon Corzine's Euro bond doubling-down call",
    "Sears — Mar 24, 2005 — Eddie Lampert merges Kmart and Sears, announces he'll run the combined company like a hedge fund",
    "Groupon — 2011 — the pre-IPO 'accounting correction' announcement",
    "WeWork — Aug 14, 2019 — the S-1 filing that killed the IPO",
    "RJR Nabisco — 1988 — the 'Premier' smokeless cigarette launch call",
    # Moved to end — same company as GM bailout (already posted Apr 28); space these out
    "General Motors — 2001 — the 57¢ ignition switch cost-cut decision",
    # Added May 2026
    "Kodak — 1975 — internal engineers invent the digital camera; management shelves it to protect film revenue; Kodak files bankruptcy 36 years later",
    "Radio Shack — 2015 — files bankruptcy; was once America's #1 consumer electronics brand with 7,000 stores",
    "Toys 'R' Us — 2000 — signs exclusive deal to sell toys only on Amazon; Amazon opens the marketplace to competitors 2 years later; Toys 'R' Us is locked in and dies",
    "Fyre Festival — Apr 27 2017 — the morning 5,000 festival-goers arrive to FEMA tents and cheese sandwiches; Billy McFarland had sold $26M in tickets for an event that didn't exist",
    # ── Added Aug 2 2026 — bank refill after the hard-duplicate-block fix. ──
    # Every entry below was fact-checked against primary sources (SEC filings,
    # CPSC releases, DOJ releases, contemporaneous press) before inclusion.
    # Corrections applied during that pass are noted inline.
    "Xerox — Dec 1979 — lets Steve Jobs see the PARC graphical interface and mouse in exchange for buying 100,000 pre-IPO Apple shares for $1M; Apple ships Lisa and Macintosh, Xerox ships the $16,595 Star in 1981 and it flops",
    # Corrected: the $100,000 offer and the 'electrical toy' memo are both
    # undocumented legend (the $100K first appears uncited in Casson 1910).
    # The documented version is Hubbard's one-sixth interest for $10,000.
    "Western Union — 1876 — president William Orton waves off Alexander Graham Bell's telephone patent as having no value except as a toy; the famous $100,000 offer is later legend, the real one was a one-sixth patent interest for $10,000",
    "Circuit City — Mar 28, 2007 — fires roughly 3,400 of its most experienced store employees for earning too much and replaces them with cheaper hires",
    # Corrected: Super Bowl ad was Jan 30 2000, BEFORE the Feb 11 IPO. The
    # widely repeated "268 days" is actually 270.
    "Pets.com — Feb 11, 2000 — IPOs at $11 a share twelve days after its sock-puppet Super Bowl ad, then announces liquidation Nov 7, 2000, roughly 270 days later",
    # Corrected: accelerated batch fermentation began in the early 1970s, not
    # 1976. The 1976 event is the Chill-garde recall. Schlitz was #2 in 1976,
    # not #1 — it lost the top spot to Budweiser in 1957.
    "Schlitz — 1976 — the Chill-garde switch reacts with its own foam stabilizer and forces a recall of 10 million bottles, capping the accelerated-fermentation era that wrecked America's #2 beer",
    # Dedup key is deliberately "Edsel", not "Ford": Ford's 2006 blue-oval
    # mortgage story is already published, and _company_posted_ever() does
    # substring matching, so a "Ford — ..." string here would be permanently
    # blocked. The Edsel is a genuinely different story, not a repeat angle.
    "Edsel — Sep 4, 1957 — Ford launches the Edsel on 'E-Day' after spending over $250M; the brand is killed Nov 19, 1959 having lost about $350M",
    "Napster — Jul 11, 2001 — court-ordered shutdown; 80 million users",
    "Pan Am — Apr 22, 1985 — agrees to sell its Pacific routes to United for $750M to cover losses; the world's most famous airline begins dismantling itself",
    "Kmart — Jan 22, 2002 — the largest retail bankruptcy in US history at the time",
    "Segway — Dec 3, 2001 — unveiled on Good Morning America after Steve Jobs called it as significant as the PC and Dean Kamen said it would be to the car what the car was to the horse and buggy",
    "Quibi — Apr 6, 2020 — launches with $1.75B raised and announces its shutdown Oct 21, 2020, about six months later",
    "Vine — Oct 27, 2016 — Twitter announces it is shutting down Vine",
    # Corrected: Motorola never went bankrupt — Iridium LLC did, Aug 13 1999.
    "Motorola — Aug 13, 1999 — Iridium LLC, the satellite phone venture Motorola built and bankrolled, files Chapter 11 nine months after launch; a $5B constellation is later sold for $25M",
    "Woolworth — Jul 17, 1997 — closes its remaining 400 US five-and-dime stores after 117 years",
    "Webvan — Jul 9, 2001 — bankruptcy after losing over $800M, including a $1B warehouse order placed with Bechtel",
    "Compaq — Jan 26, 1998 — agrees to buy Digital Equipment Corp for $9.6B; absorbed by HP four years later",
    "Smith Corona — Jul 5, 1995 — Chapter 11; the typewriter company that watched the PC arrive",
    "Peloton — May 5, 2021 — recalls the Tread+ after one child's death and 70+ injuries, three weeks after publicly calling the CPSC's urgent warning inaccurate and misleading",
    "Tower Records — Aug 20, 2006 — Chapter 11 filing; a court-ordered liquidation follows in October",

    # Added Aug 26 2026 — the 47-topic bank hit zero and the run failed with
    # TopicBankExhausted. That guard was right; the bank was just empty. One
    # topic is consumed permanently per day, so this is roughly six weeks.
    "Nokia — Feb 11, 2011 — the 'burning platform' memo, then betting the whole company on Windows Phone",
    "BlackBerry — Jan 9, 2007 — RIM's engineers watch the iPhone keynote and conclude the battery math is impossible",
    "Netscape — Nov 24, 1998 — sold to AOL after deciding to rewrite the browser from scratch",
    "Friendster — 2003 — turning down Google's offer while the site took 40 seconds to load",
    "Digg — Aug 19, 2010 — the v4 redesign ships and the users leave for Reddit inside a week",
    "Wirecard — Jun 18, 2020 — the auditors report that €1.9B in escrow does not exist",
    "HP — Aug 18, 2011 — one day: killing the TouchPad after 49 days and agreeing to buy Autonomy for $11B",
    "Commodore — Apr 29, 1994 — liquidation, a few years after the Amiga outsold everything",
    "DeLorean Motor Company — Oct 19, 1982 — the founder's arrest, with the factory already failing",
    "Sega — Jan 31, 2001 — leaving the hardware business after the Dreamcast",
    "Sun Microsystems — Apr 20, 2009 — sold to Oracle for less than it once earned in a quarter",
    "Toshiba — 2006 — buying Westinghouse, the deal that nearly ended the company a decade later",
    "Silicon Valley Bank — Mar 8, 2023 — announcing a $1.8B loss and a capital raise in the same press release",
    "Signature Bank — Mar 12, 2023 — closed by regulators two days after SVB",
    "First Republic — May 1, 2023 — seized and sold to JPMorgan before the market opened",
    "Merrill Lynch — Sep 14, 2008 — sold to Bank of America over a single weekend",
    "Credit Suisse — Mar 19, 2023 — a 167-year-old bank sold to its rival in a weekend",
    "Mt. Gox — Feb 24, 2014 — the exchange goes dark with 850,000 bitcoin unaccounted for",
    "Terra and Luna — May 9, 2022 — the stablecoin that stopped being stable",
    "Celsius Network — Jun 12, 2022 — freezing withdrawals for 1.7 million customers",
    "Volkswagen — Sep 18, 2015 — the EPA notice that named the defeat device",
    "Equifax — Sep 7, 2017 — disclosing a breach that came through a patch skipped in March",
    "Target — Dec 19, 2013 — 40 million cards taken through an air-conditioning vendor's login",
    "Robinhood — Jan 28, 2021 — restricting buys on GameStop, on the app built for buying",
    "Better.com — Dec 1, 2021 — firing 900 people on one Zoom call",
    "Juicero — Apr 19, 2017 — the video of two hands squeezing the packet",
    "Tumblr — Dec 3, 2018 — banning adult content and losing a third of its traffic",
    "Tropicana — Jan 2009 — the new carton that dropped sales 20% in two months",
    "Gap — Oct 4, 2010 — the new logo, withdrawn six days later",

    # Replacements for 8 topics dropped Aug 26 2026: they named companies
    # already present in the Format B/C pools, and the MZ ever-block is global,
    # so whichever format published first would have killed the other entry.
    "Luckin Coffee — Apr 2, 2020 — disclosing that roughly $310M of its sales were invented",
    "Thomas Cook — Sep 23, 2019 — 178 years old, and 150,000 travellers wake up stranded",
    "Solyndra — Aug 31, 2011 — shutting down with $535M of federal loan guarantees drawn",
]
# Removed from ONE_BAD_DAY (Apr 30 2026 cleanup):
# - Barings Bank (UK), Société Générale (France), Swissair (Switzerland),
#   Volkswagen (Germany) → moved to UNKNOWN_FAILURE pool (Format B only)
# - Friendster → cut entirely (too obscure, no emotional pull for US audience)
# - Polaroid → moved to NEAR_DEATH_TOPICS (better fit: invented digital, shelved it)
# - MySpace reframed: News Corp acquisition (Jul 19 2005) is the real minute zero
# - Sears reframed: Lampert merger announcement (Mar 24 2005) is the real minute zero

# ── FORMAT B: US FRAUD & SCANDAL (pivoted Apr 30 2026) ───────────────────────
# Old "Unknown Failure" foreign-company list replaced entirely.
# New premise: the FRAUD IS the story. US only. Hook rule: for lesser-known
# companies, the hook MUST lead with the most unbelievable fact — not the name.
# These are also long-form candidates: any Short that breaks out gets a
# 10-12 min deep-dive version later.

# Tier 1 — household names, fire first
UNKNOWN_FAILURE_TOPICS_TIER1 = [
    "Bernie Madoff — Dec 10, 2008 — confesses to sons Mark and Andrew; they call the FBI; $65B Ponzi scheme hidden 48 years unravels in one conversation",
    "WorldCom — Jun 25, 2002 — internal auditor Cynthia Cooper walks into the board meeting with proof of $3.8B in fake entries; Bernie Ebbers' empire gone in one afternoon",
    "Tyco International / Dennis Kozlowski — Jun 3, 2002 — resigns after DA reveals $1M art sales tax dodge; the $2M company-funded birthday party for his wife then surfaces",
    "HealthSouth / Richard Scrushy — Mar 19, 2003 — FBI raids at 5:30 AM; $2.7B fraud; Scrushy had sold $75M in stock two days prior",
    "ImClone / Martha Stewart — Dec 27, 2001 — sells 3,928 shares on an insider tip; $228K saved; ends with 5 months in federal prison",
    "Washington Mutual — Sep 25, 2008 — FDIC seizes the bank at 6 PM, sells it to JPMorgan for $1.9B by midnight; $307B in assets gone in one night",
    "Countrywide / Angelo Mozilo — 2008 — internal emails surface where Mozilo calls his own mortgage products 'toxic' and 'poison' while selling them to customers",
    "Adelphia / Rigas family — Jul 24, 2002 — John Rigas and son Timothy arrested at their Manhattan apartment; secretly borrowed $2.3B from their own public company",
    # ── Added Aug 2 2026 — fact-checked bank refill. ──
    # Corrected: the Sacklers never pleaded guilty to anything criminal — they
    # settled civilly for $225M with no admission. Only Purdue Pharma L.P. pleaded.
    "Purdue Pharma — Oct 21, 2020 — agrees to plead guilty to three federal felonies over OxyContin marketing in an $8.3B resolution, while the Sackler family settles civilly for $225M and admits nothing",
    "AIG — Sep 16, 2008 — $85B federal rescue; a London unit called AIG Financial Products had written credit default swaps that dwarfed the parent company",
    "Fannie Mae — Sep 22, 2004 — OFHEO report alleges accounting manipulation; a $6.3B restatement follows and CEO Franklin Raines is out that December",
    # Corrected: the causal order is the reverse of how this is usually told.
    # Drexel went bankrupt Feb 13 1990, ten weeks BEFORE Milken's guilty plea.
    "Drexel Burnham Lambert — Feb 13, 1990 — Wall Street's most profitable firm files for bankruptcy; ten weeks later junk bond king Michael Milken pleads guilty to six felonies",

    # Added Aug 26 2026. Checked against all four MZ pools -- the ever-block
    # is global, so a company used by one format is gone for the others.
    "Olympus / Michael Woodford — Oct 14, 2011 — the new CEO asks about $1.7B in advisory fees and is fired two weeks in",
    "Valeant — Oct 21, 2015 — a short-seller names the mail-order pharmacy Valeant secretly controlled",
    "Freddie Mac — Jun 9, 2003 — the CEO, CFO and COO all leave over earnings that were smoothed, not inflated",
    "Computer Associates / Sanjay Kumar — 2004 — the '35-day month' that held quarters open until the numbers arrived",
    "Société Générale / Jérôme Kerviel — Jan 24, 2008 — €4.9B unwound in three days from one trader's hidden positions",
    "JPMorgan / the London Whale — May 10, 2012 — a hedge meant to reduce risk loses $6.2B instead",
    "Kobe Steel — Oct 8, 2017 — admitting it had falsified strength data on metal sold for a decade",
    "Takata — Jan 13, 2017 — pleading guilty over airbag inflators the company knew could fire shrapnel",
    "Turing Pharmaceuticals / Martin Shkreli — Sep 2015 — a 62-year-old drug goes from $13.50 to $750 overnight",
    "Qwest / Joe Nacchio — 2002 — booking one-time capacity swaps as recurring revenue while selling his own shares",
]

# Tier 2 — lesser-known names, stories are insane; hook must lead with the unbelievable fact
UNKNOWN_FAILURE_TOPICS_TIER2 = [
    "ZZZZ Best / Barry Minkow — May 1987 — LA Times reporter finds no record of the $7M carpet cleaning job; a 16-year-old's $300M empire was entirely fictional",
    "Crazy Eddie — 1987 — SEC freezes assets; Eddie Antar had inflated inventory for a decade then fled to Israel; 'insane prices' was insane fraud",
    "Cendant — Apr 15, 1998 — accounting fraud discovered THREE WEEKS after the merger closed; stock drops 47% in a single day, $14B in market cap gone",
    "Global Crossing — Jan 28, 2002 — $12B bankruptcy; CEO Gary Winnick had already pocketed $700M while employees' pensions were wiped out",
    "Sunbeam / Chainsaw Al Dunlap — Jun 9, 1998 — board fires the CEO celebrated for saving companies; he'd been destroying them through accounting fraud the entire time",
    "MicroStrategy — Mar 20, 2000 — $66M restatement announced the same week as the IPO celebration; CEO Michael Saylor loses $6B in a single day",
    "Qwest / Joseph Nacchio — 2002 — CEO convicted of 19 counts of insider trading; sold $52M in stock while publicly hyping a company he knew was collapsing",
    "Symbol Technologies — 2004 — CEO Tomo Razmilovic flees to Sweden to avoid arrest for $230M fraud; FBI has to extradite him back",
    "Rite Aid — Jun 2003 — CEO Martin Grass sentenced to 8 years; $1.6B accounting fraud at the nation's third-largest drugstore chain",
    # Added May 2026
    "Nikola Motors — Sep 2020 — short seller Hindenburg Research publishes report; CEO Trevor Milton had faked a truck rolling downhill as self-driving; $35B market cap collapses in days",
    "Insys Therapeutics — 2019 — founder John Kapoor convicted of racketeering; company paid doctors cash bribes to prescribe fentanyl to patients who didn't need it; 47 dead linked to the scheme",
    "Outcome Health — 2017 — startup valued at $5.5B; executives charged with defrauding advertisers by inflating installation numbers; doctors' waiting room screens showed ads that never ran",
    # ── Added Aug 2 2026 — fact-checked bank refill. ──
    # Corrected: the bricks were shipped in autumn 1987; 1989 is when the fraud
    # was exposed. Dating the bricks to 1989 is the common distortion.
    "MiniScribe — autumn 1987 — packs 26,000 actual bricks into disk drive boxes and ships them overseas to book the revenue; the fraud is exposed in 1989 and the company is bankrupt by Jan 1990",
    "Equity Funding — 1973 — invents roughly 64,000 insurance policies on people who did not exist and sells them to reinsurers",
    # Corrected: the boxes held fruit baskets and polo shirts, not sand. The
    # "best-performing NYSE stock of 1996" line is poorly sourced — Centennial
    # only moved to the NYSE that November — so it is deliberately omitted.
    "Centennial Technologies — Feb 1997 — CEO Emanuel Pinez is arrested after the company ships fruit baskets and polo shirts booked as $2M of PC card sales; the stock is delisted in March over a $40M overstatement",
    "Peregrine Financial Group / Russell Wasendorf — Jul 9, 2012 — a suicide note confesses to 20 years of forged bank statements; $215M in customer money is gone",
    # Corrected: 21,000+ victims and $285M (not 23,000). The key detail is that
    # they bought uninsured parent-company bonds at bank branches.
    "Lincoln Savings / Charles Keating — Apr 14, 1989 — seized; more than 21,000 mostly elderly customers had been sold $285M of uninsured parent-company bonds inside bank branches; five US senators implicated",
    "Waste Management — 1998 — a $1.7B restatement, the largest in US history at the time",
    "Stanford Financial / Allen Stanford — Feb 17, 2009 — SEC charges a $7B Ponzi built on certificates of deposit from his Antiguan bank",
    "DHB Industries / David Brooks — Oct 2007 — the body armor maker's CEO is arrested for looting the company; he had thrown a $10M bat mitzvah",

    # Added Aug 26 2026. Checked against all four MZ pools -- the ever-block
    # is global, so a company used by one format is gone for the others.
    "Livent / Garth Drabinsky — Aug 1998 — the new owners open the books and find a second set",
    "Petters Group / Tom Petters — Sep 24, 2008 — an executive wears a wire and a $3.65B Ponzi unwinds",
    "Scott Rothstein — Oct 2009 — a $1.2B Ponzi built on legal settlements that did not exist",
    "Sino-Forest — Jun 2, 2011 — a short-seller reports that the timber it owns cannot be found",
    "Longtop Financial — May 2011 — the auditor resigns and says staff seized its working papers",
    "Diamond Foods — Feb 2012 — walnut payments booked into whichever year needed them",
    "Bayou Hedge Fund — 2005 — the accounting firm that signed the audits was invented by the founders",
]

NEAR_DEATH_TOPICS = [
    "Apple — Aug 6, 1997 — Steve Jobs announces Microsoft's $150M lifeline",
    "IBM — 1993 — Lou Gerstner's first board meeting, $8B loss",
    "Chrysler — 1979 — the $1.5B loan guarantee vote in Congress",
    "Disney — 1984 — Bass brothers rescue from Saul Steinberg's raid",
    "FedEx — 1973 — Fred Smith's $5K blackjack win to make Monday's payroll",
    "Starbucks — Jan 2008 — Schultz returns, closes 600 stores in one weekend",
    "Harley-Davidson — 1981 — the buyout from AMF, 13 executives' personal savings",
    "Ford — Nov 2006 — mortgaging the blue oval logo + all assets for $23.6B",
    "Converse — 2001 — Chapter 11, sold to Nike",
    "American Express — 1963 — Salad Oil Scandal, $150M exposure",
    "Delta Air Lines — Sep 14, 2005 — Chapter 11 filing at 5:30 AM",
    "Continental Airlines — 1983 & 1990 — double bankruptcy survival",
    "Best Buy — 2012 — CEO sex scandal, stock at $11, everyone wrote them off to Amazon; Hubert Joly's turnaround saves the company",
    "Netflix — Sep 18, 2011 — Qwikster split announced; 800K subscribers leave; stock drops 77%; Hastings reverses the decision",
    "Domino's — 2009 — viral 'gross ingredients' video destroys the brand; CEO goes on camera and admits the pizza was bad; radical honesty saves the company",
    "Airbnb — Mar 2020 — COVID cancels $1B in bookings overnight; company nearly collapses; pivots to Online Experiences and survives",
    # Moved from ONE_BAD_DAY Apr 30 2026 — better as near-death/missed opportunity
    "Polaroid — 1975 — engineers invent the digital camera, management shelves it; Polaroid files bankruptcy 26 years later having never shipped it",
    # Moved to end — GM bailout already posted Apr 28; space same-company stories out
    "GM — Jun 1, 2009 — Chapter 11, $82B federal bailout",
    # Added May 2026 — analytics confirm recovery/survival narratives outperform destruction
    "Marvel — 1996 — declares bankruptcy with $700M debt; Ike Perlmutter buys the company for $82.5M; goes on to build the MCU worth $53B",
    "Levi Strauss — 2003 — closes all US factories, $6B in debt; CEO Phil Marineau's turnaround saves the brand without going bankrupt",
    "Old Spice — 2008 — brand dying, P&G nearly discontinues it; 'The Man Your Man Could Smell Like' campaign reverses a decade of decline in 30 days",
    "Hostess — Nov 2012 — shuts down entirely, 18,500 jobs gone; private equity buys the brand 8 months later and brings back Twinkies",
    "Atari — 1984 — the Great Video Game Crash wipes $536M in revenue; Jack Tramiel buys the company for $50M and pivots to computers",
    # ── Added Aug 2 2026 — fact-checked bank refill. ──
    "Johnson & Johnson — Oct 1982 — seven Tylenol cyanide deaths; pulls 31 million bottles at a cost of about $100M and survives",
    # Corrected: the all-store closure was Feb 8 2016, not Oct 2015 — that was
    # the outbreak. Two separate events, commonly collapsed into one.
    "Chipotle — Feb 8, 2016 — closes every US restaurant for a day of food-safety retraining after the October 2015 E. coli outbreak drove same-store sales down nearly 30%",
    # Corrected: AMD's low was ~$1.62 in 2015, after Su took over — not $2 in 2014.
    "AMD — Oct 8, 2014 — Lisa Su takes over a chipmaker written off for dead; the stock bottoms near $1.62 in 2015 before Ryzen and EPYC rebuild it",
    "Tesla — Dec 24, 2008 — a $40M financing round closes on Christmas Eve, days before Tesla would have missed payroll",
    # Corrected: the $183.6M loss was fiscal 2008, disclosed in the Mar 2009
    # 10-K with going-concern doubt. The 2009 loss was far smaller (~$42M).
    "Crocs — Mar 2009 — files a 10-K showing a $183.6M loss for 2008 with going-concern doubt; the shoe everyone called a fad is written off as dead",
    "Barnes & Noble — Jun 7, 2019 — agrees to sell itself to Elliott for $683M; James Daunt hands buying power back to individual stores",
    # Corrected: the plane sale was spring 1972 for operating capital, not 1971
    # "to make payroll" — and it is what forced the ten-minute turn.
    "Southwest Airlines — spring 1972 — down to $143 in the bank a year after launching, sells one of its four planes and invents the ten-minute turn to fly the same schedule with three",
    # Corrected: the SEC investigation opened Oct 2004; the restatement was Jan 2005.
    "Krispy Kreme — Oct 2004 — the SEC opens a formal accounting investigation after overexpansion; a January 2005 restatement wipes out $25M of income and the stock collapses",
    "Six Flags — Jun 13, 2009 — Chapter 11 with $2.4B in debt",
    "Uber — 2017 — a year of scandals ends with Travis Kalanick out in June and Dara Khosrowshahi in by August",
    "Papa John's — Jul 11, 2018 — founder John Schnatter resigns as chairman after Forbes reports he used a racial slur on a conference call; the brand rebuild follows",
    "Dell — Oct 29, 2013 — Michael Dell and Silver Lake complete a $24.9B buyout to take the company private and fix it away from public markets",

    # Added Aug 26 2026. Checked against all four MZ pools -- the ever-block
    # is global, so a company used by one format is gone for the others.
    "Lego — 2004 — a 35-year-old outsider takes over a company losing money on nearly every set it sells",
    "Nintendo — 2014 — the Wii U stalls and Nintendo posts its first operating loss in three decades",
    "Nvidia — 1996 — the NV1 fails and there is money in the bank for exactly one more chip",
    "Pixar — 1991 — weeks from shutdown when Disney signs a three-picture deal",
    "Fujifilm — 2000 — film revenue starts falling off a cliff and the company bets on chemicals and cosmetics",
    "Sony — 2012 — a $6.4B annual loss, credit downgraded to near junk, and a new CEO selling the buildings",
    "Gucci — 1993 — the last family shareholder sells out with the brand sitting on discount racks",
    "Hertz — May 22, 2020 — Chapter 11 with the fleet parked, then a share rally nobody could explain",
    "GameStop — Jan 2021 — days from a restructuring conversation when the share price went vertical",
    "Burberry — 2006 — the check had become a liability and the brand had to buy back its own licences",
    "Aston Martin — 1992 — production falls below 50 cars for the year",
    "Porsche — 1992 — down to weeks of cash before the factory was rebuilt around Toyota's methods",
]
# Removed from NEAR_DEATH (Apr 30 2026 cleanup):
# - Marvel → already posted Apr 28, removed to prevent duplicate
# - LEGO (Danish), Nintendo (Japanese), Harrods (UK) → foreign companies cut
# - J.Crew → weak story, "COVID hit retail" has no compelling human element
# - GM moved to end (same company as Apr 28 bailout video — space them out)


# ── Household brand tier (for Format A weighting) ─────────────────────────────
# Analytics confirm: iconic household names (Boeing, FedEx, GM, Marvel, Kodak)
# dramatically outperform obscure companies. Weight them 3× in random selection.
MZ_HOUSEHOLD_BRANDS = {
    "knight capital", "coca-cola", "yahoo", "blockbuster", "quaker oats",
    "jcpenney", "aol", "enron", "theranos", "ftx", "long-term capital",
    "arthur andersen", "borders", "wells fargo", "boeing", "myspace",
    "bear stearns", "lehman brothers", "sears", "groupon", "wework",
    "rjr nabisco", "general motors", "kodak", "radio shack", "toys r us",
    "fyre festival", "apple", "ibm", "chrysler", "disney", "fedex",
    "starbucks", "harley", "ford", "american express", "delta", "netflix",
    "best buy", "domino's", "airbnb", "marvel", "polaroid", "gm",
    "bernie madoff", "worldcom", "tyco", "imclone", "martha stewart",
    "washington mutual", "countrywide", "adelphia", "nikola",
    # Added Aug 2 2026 with the bank refill — recognisable names get the 3× weight.
    "xerox", "western union", "circuit city", "kmart", "napster", "pan am",
    "woolworth", "motorola", "compaq", "peloton", "tower records", "edsel",
    "segway", "quibi", "vine", "pets.com", "smith corona", "webvan",
    "johnson & johnson", "chipotle", "tesla", "crocs", "barnes & noble",
    "southwest airlines", "krispy kreme", "six flags", "uber", "papa john's",
    "dell", "amd", "aig", "fannie mae", "purdue pharma",
}

# Warn when a format's never-posted pool drops to this many topics or fewer.
MZ_LOW_POOL_THRESHOLD = 5


class TopicBankExhausted(RuntimeError):
    """Every company in a format's topic pool already has a published video.

    Raised instead of silently re-publishing a duplicate (Aug 2 2026 fix).
    """


def _extract_company_name(topic: str) -> str:
    """Extract company name from topic string (text before first ' — ')."""
    raw = topic.split(" — ")[0].strip()
    # Strip leading date-like tokens (e.g. "FTX — Nov 2..." → raw = "FTX")
    name = raw.lower()
    # Normalize punctuation so "Toys 'R' Us" and "Toys R Us" are recognized as
    # the SAME company for dedup purposes. Fixed Jul 19 2026: apostrophes/quotes
    # in AI-generated topic strings broke the substring match in
    # _company_posted_ever()/_company_posted_recently(), letting Toys R Us
    # repost under a differently-punctuated topic string (confirmed leak,
    # weekly review Jul 19 2026).
    for ch in ("'", "’", "‘", '"', "“", "”"):
        name = name.replace(ch, "")
    name = " ".join(name.split())
    return name


# Genuine same-company abbreviations. The old substring matcher claimed to
# catch these ("General Motors" vs "GM") but never could — "gm" is not a
# substring of "general motors".
_COMPANY_ALIASES = {
    "gm": "general motors",
}

# Dropped before comparison so "Tyco International" matches "Tyco".
_COMPANY_STOPWORDS = {
    "the", "inc", "corp", "corporation", "company", "co", "group",
    "holdings", "llc", "lp", "ltd", "plc", "and",
}


def _company_tokens(name: str) -> frozenset:
    """Normalise a company key to a set of comparable word tokens."""
    name = (name or "").strip().lower()
    name = _COMPANY_ALIASES.get(name, name)
    toks = {t for t in re.split(r"[^a-z0-9]+", name) if t}
    stripped = toks - _COMPANY_STOPWORDS
    # Never return empty for a name that was purely stopwords.
    return frozenset(stripped or toks)


def _same_company(a: str, b: str) -> bool:
    """True if two company keys refer to the same company.

    Token-subset match, not substring. Fixed Aug 2 2026: the previous
    `a in b or b in a` test blocked "Stanford Financial" because the published
    company "Ford" is a substring of "stanFORD". Subset matching still catches
    the intended cases — "Tyco" vs "Tyco International / Dennis Kozlowski" —
    without matching on accidental letter runs.
    """
    ta, tb = _company_tokens(a), _company_tokens(b)
    if not ta or not tb:
        return False
    return ta <= tb or tb <= ta


def _company_posted_recently(company_name: str, days: int = 30) -> bool:
    """True if the same company was posted (short or longform) in the last 30 days.
    Prevents FTX 3× or Blockbuster 2× within a rolling month."""
    log = _load_log()
    cutoff = dt.datetime.now() - dt.timedelta(days=days)
    company_lc = company_name.lower()
    for post in log.get("posts", []):
        if post.get("channel") != "mz":
            continue
        try:
            post_dt = dt.datetime.strptime(post.get("posted_at", ""), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if post_dt < cutoff:
            continue
        # Check company name in post's topic string
        post_company = _extract_company_name(post.get("topic", ""))
        if _same_company(company_lc, post_company):
            return True
    return False


def _company_posted_ever(company_name: str) -> bool:
    """True if the same company has ever been posted on MZ (any date).
    Enforces the no-duplicate-angle rule: one definitive video per company.
    Returns False (allow) only if the company has never appeared in the log."""
    log = _load_log()
    company_lc = company_name.lower()
    for post in log.get("posts", []):
        if post.get("channel") != "mz":
            continue
        post_company = _extract_company_name(post.get("topic", ""))
        if _same_company(company_lc, post_company):
            return True
    return False


def _is_household_brand(topic: str) -> bool:
    """True if the topic's company is an iconic household name."""
    company = _extract_company_name(topic)
    for brand in MZ_HOUSEHOLD_BRANDS:
        if _same_company(company, brand):
            return True
    return False


# ── Short→Longform amplification queue ────────────────────────────────────────

def load_longform_queue() -> list:
    """Load the list of high-performing short topics queued for long-form."""
    if LONGFORM_QUEUE_FILE.exists():
        try:
            return json.loads(LONGFORM_QUEUE_FILE.read_text())
        except Exception:
            pass
    return []


def save_longform_queue(queue: list) -> None:
    LONGFORM_QUEUE_FILE.write_text(json.dumps(queue, indent=2))


def queue_for_longform(topic: str, title: str, video_url: str,
                       short_views: int, threshold: int = 700) -> bool:
    """If a short crosses the view threshold, add to longform queue.
    Called by the daily monitor after checking analytics (7 days post-publish).
    Returns True if queued."""
    if short_views < threshold:
        return False
    queue = load_longform_queue()
    # Don't double-queue the same topic
    existing_topics = {item.get("topic", "") for item in queue}
    if topic in existing_topics:
        return False
    queue.append({
        "topic":      topic,
        "title":      title,
        "short_url":  video_url,
        "views":      short_views,
        "queued_at":  time.strftime("%Y-%m-%d %H:%M:%S"),
        "status":     "pending",  # → "used" when longform posts
    })
    save_longform_queue(queue)
    print(f"  📋 Queued for long-form (views={short_views}): {topic[:60]}...")
    return True


# ─── Rotation logic ──────────────────────────────────────────────────────────

def pick_format_for_slot(weekday: int, hour_ct: int) -> str:
    """
    Rotation from MZ_Channel #3 plan:
      09:00 CT daily  → Format A (one_bad_day)
      19:00 CT Mon/Wed/Fri/Sun → Format B (unknown_failure)
      19:00 CT Tue/Thu/Sat     → Format C (near_death)

    weekday: Python datetime.weekday() (Monday=0 ... Sunday=6)
    hour_ct: hour in Central Time (24h)
    """
    if hour_ct < 12:
        return "A"
    # Evening slot
    # Mon=0, Wed=2, Fri=4, Sun=6  → Format B
    # Tue=1, Thu=3, Sat=5         → Format C
    if weekday in (0, 2, 4, 6):
        return "B"
    return "C"


def pick_topic(format_letter: str) -> tuple[str, str]:
    """Return (topic_string, format_tag_for_prompt).

    Guardrails applied:
    - 30-day company-name dedup across ALL MZ posts (short + longform)
      prevents FTX 3×, Blockbuster 2×, etc.
    - Format A (ONE_BAD_DAY): household brand topics weighted 3× over obscure ones.
    - Format B (UNKNOWN_FAILURE): Tier 1 (household names) exhausted before Tier 2.
    """
    log = _load_log()
    used = set(log.get("mz_topics_used", []))

    if format_letter == "A":
        pool = ONE_BAD_DAY_TOPICS
        tag = "one_bad_day"
    elif format_letter == "B":
        # Exhaust Tier 1 before dipping into Tier 2
        tier1_available = [t for t in UNKNOWN_FAILURE_TOPICS_TIER1 if t not in used]
        tier2_available = [t for t in UNKNOWN_FAILURE_TOPICS_TIER2 if t not in used]
        pool = tier1_available if tier1_available else tier2_available
        if not pool:
            pool = UNKNOWN_FAILURE_TOPICS_TIER1 + UNKNOWN_FAILURE_TOPICS_TIER2
        tag = "unknown_failure"
    elif format_letter == "C":
        pool = NEAR_DEATH_TOPICS
        tag = "near_death"
    else:
        raise ValueError(f"Invalid format letter: {format_letter}")

    # ── Apply HARD company dedup: one definitive video per company, ever ──────
    # Fixed Aug 2 2026. Previously the filter used a 30-day window and
    # _company_posted_ever() only printed a warning — so Kodak (70 days apart)
    # and Blockbuster (83 days apart) both re-posted. Confirmed duplicates in
    # the Jul 31 / Aug 1 weekly review: Kodak, Blockbuster, Bear Stearns,
    # Yahoo, Arthur Andersen. The ever-block is now the actual filter, which
    # is what this module's docstrings claimed all along.
    available = [
        t for t in pool
        if t not in used
        and not _company_posted_ever(_extract_company_name(t))
    ]

    # ── Low-pool early warning ────────────────────────────────────────────────
    # With a hard ever-block the bank drains permanently, so warn BEFORE the
    # exhaustion path forces a compromise.
    if 0 < len(available) <= MZ_LOW_POOL_THRESHOLD:
        # ::warning:: so this lands as an annotation on the Actions run summary.
        # Aug 26 2026: the bank drained to zero and nobody saw this line, because
        # a plain print only exists inside a log nobody opens on a green run.
        print(f"::warning::MZ TOPIC BANK LOW -- only {len(available)} unused, "
              f"never-posted topic(s) left for Format {format_letter}. "
              f"Format A burns one per day. Add new topics now.")

    if not available:
        # Clear this format's used-set — a topic may be marked used without ever
        # having been published (validator skips, fallbacks), so recover those first.
        print(f"  🔄 All MZ Format {format_letter} topics marked used — resetting cycle")
        for t in pool:
            used.discard(t)
        log["mz_topics_used"] = list(used)
        _save_log(log)
        # Re-apply the HARD ever-block. Only topics never actually published
        # are eligible — this recovers skipped topics without re-serving
        # anything that already has a video live.
        available = [
            t for t in pool
            if not _company_posted_ever(_extract_company_name(t))
        ]

    if not available:
        # Genuine exhaustion: every company in this pool already has a video.
        # Refuse to publish a duplicate — that is the bug we just fixed.
        # Format B has a second tier and main() has a Format-B fallback, so a
        # clean skip is safe and strictly better than a repeat.
        raise TopicBankExhausted(
            f"MZ Format {format_letter}: every topic in the pool has already been "
            f"published. Add new topics to the bank — refusing to post a duplicate."
        )

    # ── Format A: weight household brands 3× ─────────────────────────────────
    if format_letter == "A" and available:
        weights = [3 if _is_household_brand(t) else 1 for t in available]
        chosen = random.choices(available, weights=weights, k=1)[0]
        brand_label = "household" if _is_household_brand(chosen) else "obscure"
        print(f"  🏢 MZ Format A topic selected [{brand_label}]: {chosen[:70]}...")
        return chosen, tag

    return random.choice(available), tag


# ─── Log helpers ─────────────────────────────────────────────────────────────

def _load_log() -> dict:
    """Load MZ log from per-channel file (primary), merging shared log for compat."""
    data: dict = {"posts": [], "mz_topics_used": []}
    if MZ_LOG_FILE.exists():
        try:
            data = json.loads(MZ_LOG_FILE.read_text())
        except Exception:
            pass
    # Merge any MZ entries from the shared log not yet in the per-channel file
    if LOG_FILE.exists():
        try:
            shared = json.loads(LOG_FILE.read_text())
            existing_ats = {p.get("posted_at") for p in data.get("posts", [])}
            for p in shared.get("posts", []):
                if p.get("channel") == "mz" and p.get("posted_at") not in existing_ats:
                    data.setdefault("posts", []).append(p)
        except Exception:
            pass
    return data


def _save_log(log: dict) -> None:
    """Save to per-channel MZ log file (primary) and update shared log (compat)."""
    MZ_LOG_FILE.write_text(json.dumps(log, indent=2))
    try:
        shared: dict = {"posts": []}
        if LOG_FILE.exists():
            shared = json.loads(LOG_FILE.read_text())
        shared_ats = {p.get("posted_at") for p in shared.get("posts", []) if p.get("channel") == "mz"}
        for p in log.get("posts", []):
            if p.get("posted_at") not in shared_ats:
                shared.setdefault("posts", []).append(p)
        LOG_FILE.write_text(json.dumps(shared, indent=2))
    except Exception:
        pass


def append_to_google_sheets(title: str, url: str, format_tag: str) -> None:
    """Append posted MZ video to Google Sheets Auto-Post Log (GitHub Actions only)."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from datetime import datetime
        from zoneinfo import ZoneInfo
    except ImportError:
        print("⚠️  Google API libraries not available for Sheets logging")
        return
    try:
        creds_json = os.environ.get("GOOGLE_SHEETS_KEY")
        if not creds_json:
            print("  ❌ GOOGLE_SHEETS_KEY not set — skipping Sheets log")
            return
        creds = service_account.Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        timestamp = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M:%S")
        row = [timestamp, "Minute Zero", title, "Success", url, ""]
        service.spreadsheets().values().append(
            spreadsheetId="1JKlBnYdv-_r3FcjozBtpRxLNRiAoA1ezLRz2W-7vVWI",
            range="Auto-Post Log!A:G",
            valueInputOption="USER_ENTERED",
            body={"values": [row]}
        ).execute()
        print(f"  📊 Logged to Google Sheets: Minute Zero — {title}")
    except Exception as e:
        print(f"  ⚠️  Sheets logging failed: {str(e)[:100]}")


def mark_mz_posted(topic: str, title: str, video_url: str, format_tag: str) -> None:
    log = _load_log()
    log.setdefault("mz_topics_used", []).append(topic)
    log.setdefault("posts", []).append({
        "channel":    "mz",
        "format":     format_tag,
        "topic":      topic,
        "title":      title,
        "url":        video_url,
        "posted_at":  time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_log(log)


# ─── MZ Script validators ────────────────────────────────────────────────────

# edge-tts ChristopherNeural speaks at ~2.5 words/sec.
# Calibrated May 6 2026 from Washington Mutual video (106w → 54.5s = 1.95 wps observed,
# but script was underfilled; 2.5 wps is the correct target for a properly-filled script).
MZ_WORD_TARGETS = {
    "one_bad_day":     (130, 165),   # Format A: target 52–66s (floor lowered 140→130 Jun 30 — DeepSeek lands ~137)
    "unknown_failure": (170, 215),   # Format B: target 68–86s (floor lowered 180→170 Jun 30 — DeepSeek lands ~178)
    "near_death":      (155, 215),   # Format C: target 62–86s (floor lowered 165→155 Jun 30 to match)
}

def mz_script_word_count_ok(script: dict, format_tag: str) -> tuple[bool, int, tuple[int, int]]:
    """Check narration word count is in the edge-tts target band for this format.

    MZ uses a flat 'script' string field (not scenes like TMF).
    Returns (ok, actual_count, (min, max)).
    """
    narration = (script.get("script") or "").strip()
    total = len(narration.split())
    lo, hi = MZ_WORD_TARGETS.get(format_tag, (140, 215))
    return (lo <= total <= hi), total, (lo, hi)


def mz_title_ok(title: str) -> tuple[bool, str]:
    """MZ title guardrails — data-backed from analytics (May 2026).

    Proven winners:
      Pattern 1 — "How [X]...":  "How One Buyout Saved Harley-Davidson" (919 views), "How Marvel Survived" (all-time #1)
      Pattern 2 — Number/$:      "$440M Gone in 12 Minutes", "31 Minutes That Shattered Groupon"
      Pattern 3 — "The [X] That [Verb]ed": "The Weekend That Killed Lehman", "The Phone Call That Killed Blockbuster"

    Confirmed losers (banned):
      "The Night..." (83 views), "The Day..." (weak), "The Moment..." (underperformed), "The Hour...", bare "The Week..."
    """
    t = (title or "").strip()
    if len(t) < 10:
        return False, "title too short"
    if len(t) > 70:
        return False, f"title too long ({len(t)} chars — keep under 70)"

    t_lower = t.lower()
    words = t_lower.split()

    # Ban confirmed weak openers — use exact first-two-word match to avoid
    # accidentally blocking "the weekend" (which starts with "the week").
    banned_first_two = {"the night", "the day", "the moment", "the hour"}
    first_two = " ".join(words[:2])
    if first_two in banned_first_two:
        return False, (
            f"title starts with '{first_two}' — confirmed underperformer. "
            f"Use 'How [Company] Survived/Died', a dollar/number lead, or "
            f"'The [X] That [Verb]ed [Company]'. "
            f"Example: 'The Weekend That Killed Lehman Brothers'"
        )
    # Also ban bare "the week" but NOT "the weekend" (The Weekend That Killed Lehman = winner)
    if t_lower.startswith("the week ") and not t_lower.startswith("the weekend"):
        return False, (
            "title starts with 'the week' — confirmed underperformer. "
            "Use 'The Weekend That...' or reframe as 'How [Company]...'"
        )

    # Pattern 1: "How [X]..." — proven #1 opener
    starts_with_how = t_lower.startswith("how ")

    # Pattern 2: dollar/number in the first 5 words
    first_five = " ".join(words[:5])
    has_number_or_dollar = any(c.isdigit() or c == "$" for c in first_five)

    # Pattern 3: "The [X] That [Verb]ed [Company]" — proven winner (May 2026 analytics)
    # "The Weekend That Killed Lehman", "The Phone Call That Killed Blockbuster",
    # "The 31 Minutes That Shattered Groupon"
    the_x_that = t_lower.startswith("the ") and " that " in t_lower

    if not (starts_with_how or has_number_or_dollar or the_x_that):
        return False, (
            f"title must use a proven pattern: "
            f"(1) start with 'How', "
            f"(2) lead with a dollar/number figure, or "
            f"(3) 'The [X] That [Verb]ed [Company]' structure. "
            f"Got: \"{t[:50]}\". "
            f"Good: 'How Harley Survived', '$440M Gone in 12 Minutes', 'The Call That Killed Blockbuster'"
        )

    return True, ""


# Banned generic Pexels terms that recur across every video and produce
# visually identical dark-city / corporate-building footage.
_PEXELS_BANNED_TERMS = {
    "dark city", "city night", "night city", "office building",
    "corporate headquarters", "businessman", "businessmen",
    "business meeting", "financial stress", "money", "finance",
    "economy", "economic", "growth", "failure", "corporate",
    "city skyline", "skyscraper", "downtown", "urban night",
}

def mz_pexels_queries_ok(script: dict) -> tuple[bool, str]:
    """Check that every Pexels query is topic-specific, not a banned generic phrase.

    Each query must:
      1. Not consist entirely of banned generic terms.
      2. Contain at least one word that is 4+ chars and NOT in the banned set,
         so GPT can't sneak in "dark city skyline" and call it specific.
    Returns (ok, problem_description).
    """
    queries = script.get("pexels_search_queries") or []
    if not queries:
        return False, "pexels_search_queries is missing or empty"

    bad_queries = []
    for q in queries:
        q_lower = q.lower().strip()
        words = set(w.strip(".,;:\"'") for w in q_lower.split())
        # A query is "generic" if every meaningful word (4+ chars) is in the banned set
        meaningful = [w for w in words if len(w) >= 4]
        if meaningful and all(w in _PEXELS_BANNED_TERMS for w in meaningful):
            bad_queries.append(q)
            continue
        # Also flag if a banned multi-word phrase is the ENTIRE query (2–3 word queries)
        if any(q_lower == banned or q_lower.startswith(banned + " ") or q_lower.endswith(" " + banned)
               for banned in _PEXELS_BANNED_TERMS if " " in banned):
            bad_queries.append(q)

    if bad_queries:
        return False, (
            f"PEXELS QUERY FAIL: {len(bad_queries)} generic query/queries that will produce "
            f"repeated dark-city/corporate footage: {bad_queries}. "
            f"Every query MUST contain a company name, person, location, or specific year. "
            f"BAD: 'dark city night' — GOOD: 'WeWork coworking office 2019'"
        )
    return True, ""


# ─── Script generation (v3 prompt → JSON) ────────────────────────────────────

def load_system_prompt() -> str:
    """Read v3 prompt markdown and extract the code-block payload."""
    if not MZ_PROMPT_V3.exists():
        raise FileNotFoundError(f"Missing v3 prompt: {MZ_PROMPT_V3}")
    text = MZ_PROMPT_V3.read_text()
    # The prompt lives inside a ```...``` code fence
    in_block = False
    lines: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("```") and not in_block:
            in_block = True
            continue
        if line.strip().startswith("```") and in_block:
            break
        if in_block:
            lines.append(line)
    if not lines:
        raise RuntimeError("Could not extract code block from v3 prompt file")
    return "\n".join(lines)


def _call_deepseek(system: str, user: str) -> str:
    """Call DeepSeek V3 (OpenAI-compatible API). ~95% cheaper than GPT-4o."""
    from openai import OpenAI
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is missing or empty")
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    r = client.chat.completions.create(
        model="deepseek-v4-flash",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.8,
    )
    return r.choices[0].message.content


def _call_openai(system: str, user: str) -> str:
    """Call OpenAI and return raw content string."""
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing or empty")
    client = OpenAI(api_key=api_key)
    r = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.8,
    )
    return r.choices[0].message.content


def _call_anthropic(system: str, user: str) -> str:
    """Call Anthropic and return raw content string."""
    from anthropic import Anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is missing or empty")
    client = Anthropic(api_key=api_key)
    r = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return r.content[0].text


def _parse_llm_content(content: str) -> dict:
    """Parse JSON from LLM response, stripping any markdown code fences."""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].lstrip()
    data = json.loads(content)
    if "error" in data:
        raise RuntimeError(f"Script generator self-rejected: {data['error']}")
    return data


def generate_script(topic: str, format_tag: str) -> dict:
    """Call the LLM backend with v3 prompt + tagged topic, return validated JSON.

    Primary backend: OpenAI (proven, paid, reliable).
    Fallback backend: Anthropic (used if OpenAI fails for any reason).
    MZ_MODEL_BACKEND env var can force a specific backend, but fallback still applies.

    Validator: up to 3 attempts. Rejects scripts where narration word count falls
    outside the edge-tts target band for the given format.
    """
    system = load_system_prompt()
    user_base = f"[{format_tag.upper()}] {topic}"

    # Determine call order based on available keys + MODEL_BACKEND setting.
    # Priority: DeepSeek (95% cheaper, same quality) → OpenAI → Anthropic
    deepseek_available = bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())
    if MODEL_BACKEND == "anthropic":
        primary_fn,  primary_name  = _call_anthropic, "anthropic"
        fallback_fn, fallback_name = _call_openai,    "openai"
    elif deepseek_available:
        primary_fn,  primary_name  = _call_deepseek, "deepseek-v4-flash"
        fallback_fn, fallback_name = _call_openai,   "openai"
    else:
        primary_fn,  primary_name  = _call_openai,    "openai"
        fallback_fn, fallback_name = _call_anthropic,  "anthropic"

    def _call_with_fallback(system_prompt: str, user_msg: str) -> dict:
        """Try primary backend, fall back to secondary on any error."""
        try:
            print(f"  🤖 Using {primary_name} backend ...")
            content = primary_fn(system_prompt, user_msg)
            return _parse_llm_content(content)
        except Exception as e:
            print(f"  ⚠️  {primary_name} failed: {str(e)[:120]}")
            print(f"  🔄 Falling back to {fallback_name} ...")
        try:
            content = fallback_fn(system_prompt, user_msg)
            print(f"  ✅ {fallback_name} fallback succeeded")
            return _parse_llm_content(content)
        except Exception as e2:
            raise RuntimeError(
                f"Both LLM backends failed.\n"
                f"  {primary_name}: see above\n"
                f"  {fallback_name}: {str(e2)[:200]}"
            ) from e2

    extra = ""
    last_data: dict | None = None
    lo, hi = MZ_WORD_TARGETS.get(format_tag, (140, 215))

    for attempt in range(1, 4):   # up to 3 attempts
        data = _call_with_fallback(system + extra, user_base)
        last_data = data

        wc_ok, word_count, (lo, hi) = mz_script_word_count_ok(data, format_tag)
        title_ok, title_reason = mz_title_ok(data.get("title", ""))
        pexels_ok, pexels_reason = mz_pexels_queries_ok(data)

        problems = []
        if not wc_ok:
            est_sec = int(word_count / 2.5)
            direction = "too long" if word_count > hi else "too short"
            problems.append(
                f"LENGTH FAIL ({direction}): narration is {word_count} words (~{est_sec}s at edge-tts rate). "
                f"Must be {lo}–{hi} words (target {int(lo/2.5)}–{int(hi/2.5)}s)."
            )
        if not title_ok:
            problems.append(f"TITLE FAIL: {title_reason}")
        if not pexels_ok:
            problems.append(pexels_reason)

        if not problems:
            print(f"  ✅ Script passed validators ({word_count}w, title OK) on attempt {attempt}")
            return data

        print(f"  ⚠️  Validator failed attempt {attempt}/3: {' | '.join(problems)}")

        # Build a targeted hint for LENGTH FAIL — direction matters.
        # Under limit: expand minute_zero with specific detail checklist.
        # Over limit: trim — removing filler is more effective than generic "shorten".
        length_hint = ""
        if not wc_ok:
            rejected_script = (data.get("script") or "").strip()
            if word_count < lo:
                need_more = lo - word_count
                length_hint = (
                    f"\n\nYour rejected narration ({word_count} words) is shown below. "
                    f"You must ADD at least {need_more} more words — NOT by repeating or padding, "
                    f"but by expanding the minute_zero beat with:\n"
                    f"  • The exact date/time the crisis peaked\n"
                    f"  • Specific dollar figures or numeric thresholds\n"
                    f"  • Who made the key decision and what they actually did\n"
                    f"  • What would have happened if they had waited 24 more hours\n"
                    f"  • The emotional/internal state inside the company at that moment\n"
                    f"Keep all other beats as-is. Only expand minute_zero.\n\n"
                    f"REJECTED SCRIPT:\n{rejected_script}"
                )
            else:  # word_count > hi — script is too long, need to trim
                need_cut = word_count - hi
                length_hint = (
                    f"\n\nYour rejected narration ({word_count} words) is shown below — it is "
                    f"{need_cut} words TOO LONG. You must CUT {need_cut}+ words by:\n"
                    f"  • Removing throat-clearing phrases and filler transitions\n"
                    f"  • Compressing the setup beat — one punchy sentence per fact, not two\n"
                    f"  • Cutting redundant restatements of the same idea\n"
                    f"  • Trimming the past_greatness beat to 1–2 sentences max\n"
                    f"Do NOT cut the minute_zero beat — that is the payoff. Cut setup and framing.\n\n"
                    f"REJECTED SCRIPT:\n{rejected_script}"
                )

        trim_or_expand = "Do NOT pad or summarise." if word_count < lo else "Do NOT add new content — trim existing sentences."
        extra = (
            "\n\nIMPORTANT — your previous draft was REJECTED:\n- "
            + "\n- ".join(problems)
            + f"\n\nFix ALL issues. The narration (script field) MUST be {lo}–{hi} words. "
              f"edge-tts speaks at ~2.5 words/sec — {lo}w = ~{int(lo/2.5)}s, {hi}w = ~{int(hi/2.5)}s. "
            + trim_or_expand
            + length_hint
        )

    # All retries exhausted — skip this post rather than publish a bad title.
    # Caller catches TITLE_VALIDATION_SKIP, logs to Sheets, and exits 0 (green in GH Actions).
    last_title = (last_data or {}).get("title", "n/a") if last_data else "n/a"
    raise ValueError(
        f"TITLE_VALIDATION_SKIP: all 3 attempts failed — "
        f"last title: \"{last_title}\" | word count: {word_count}"
    )


# ─── Subscribe CTA (Shorts) ──────────────────────────────────────────────────
# Added Aug 2 2026. MZ had NO subscribe ask anywhere: 17,873 views → 25 subs
# (0.14% view-to-sub; healthy Shorts channels run 0.5-1%).
#
# Design constraint: v3 prompt rule #1 is the loop-design final line (the last
# story sentence must trigger a rewatch). The CTA is appended AFTER that line
# as a separate tag so the rewatch hook still closes the narrative, and it is
# written as a curiosity loop of its own ("the next one") rather than a bare
# "please subscribe" — giving a reason-why instead of an ask.
#
# Set MZ_SUB_CTA=0 to disable and A/B against the 0.14% baseline.

MZ_SUB_CTAS = [
    "Every empire has a minute zero. Subscribe before the next one.",
    "There's another collapse tomorrow. Subscribe and watch it happen.",
    "One company. One bad day. Every day. Subscribe.",
    "The next empire is already breaking. Subscribe to catch it.",
    "Somewhere, another minute zero just started. Subscribe.",
]


def append_sub_cta(script_data: dict, topic: str) -> tuple[dict, str | None]:
    """Append a spoken subscribe CTA to the narration. Returns (script_data, cta).

    Called after validators pass so the word-count band is untouched. Rotates
    deterministically on the topic string so the same company always gets the
    same CTA (stable re-runs) but consecutive uploads vary.
    """
    if os.environ.get("MZ_SUB_CTA", "1").strip() == "0":
        print("  ⏭️  Spoken subscribe CTA disabled (MZ_SUB_CTA=0)")
        return script_data, None

    cta = MZ_SUB_CTAS[sum(ord(c) for c in topic) % len(MZ_SUB_CTAS)]
    narration = (script_data.get("script") or "").rstrip()
    if not narration:
        print("  ⚠️  Empty narration — skipping subscribe CTA")
        return script_data, None

    if not narration.endswith((".", "!", "?", '"')):
        narration += "."
    script_data["script"] = f"{narration} {cta}"

    added = len(cta.split())
    print(f"  📣 Subscribe CTA appended (+{added}w, ~+{added / 2.5:.1f}s): \"{cta}\"")
    return script_data, cta


# ─── Pinned comment (Shorts) ─────────────────────────────────────────────────

MZ_COMMENT_QUESTIONS = [
    "Which collapse should I cover next? Drop a company below.",
    "Could this one have been survived? Tell me where they went wrong.",
    "What's the most avoidable business failure you can think of?",
    "Name a company you think is one bad day away right now.",
    "Did you know this story, or is this the first you're hearing it?",
]


def post_mz_channel_comment(video_id: str, topic: str = "") -> None:
    """Post the pinned comment on every MZ Short. Pin manually in Studio.

    Rewritten Aug 2 2026. Previously 100% Audible affiliate, zero subscribe ask
    — on a channel with 88 subs that link converts ~nothing, while the pinned
    comment is the highest-intent conversion surface a Short has.

    Now: subscribe ask + an open question. The question also targets the
    zero-engagement signal flagged in the Aug 2 digest — Shorts with no
    comments read as low-quality to the ranker, and a pinned question is the
    cheapest legitimate way to seed replies.

    Affiliate link intentionally removed from Shorts comments; it remains in
    the video description. Restore it here once the channel is monetized.
    """
    question = MZ_COMMENT_QUESTIONS[
        sum(ord(c) for c in (topic or video_id)) % len(MZ_COMMENT_QUESTIONS)
    ]
    comment_text = (
        f"{question}\n\n"
        "\U0001f4c9 New business collapse every day — subscribe so you don't miss "
        "the next minute zero."
    )
    try:
        import json as _json
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        token_path = BASE_DIR / "youtube_token_mz.json"
        creds = Credentials.from_authorized_user_file(str(token_path),
            ["https://www.googleapis.com/auth/youtube.upload",
             "https://www.googleapis.com/auth/youtube",
             "https://www.googleapis.com/auth/youtube.force-ssl"])  # required for commentThreads().insert()
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        youtube = build("youtube", "v3", credentials=creds)
        youtube.commentThreads().insert(
            part="snippet",
            body={"snippet": {"videoId": video_id,
                              "topLevelComment": {"snippet": {"textOriginal": comment_text}}}}
        ).execute()
        print(f"  ✅ Pinned comment posted (subscribe + question) — PIN IT in Studio!")
    except Exception as e:
        print(f"  ⚠️  Short pinned comment failed (non-fatal): {e}")


# ─── YouTube upload ──────────────────────────────────────────────────────────

def upload_to_youtube(video_path: Path, title: str, description: str,
                      tags: list[str], thumbnail_path: Path | None = None,
                      privacy_status: str = "public") -> str:
    """Upload the MZ master to YouTube. Returns video URL.

    privacy_status: "public" (default, used by cron), "unlisted" (manual
    routing test — video uploads but doesn't appear in feed/search), or
    "private" (only owner can view).
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    token_path = BASE_DIR / "youtube_token_mz.json"
    if not token_path.exists():
        raise RuntimeError("youtube_token_mz.json missing — complete OAuth first")

    # NOTE: upload itself doesn't need force-ssl (that's only required for
    # commentThreads().insert(), done separately in post_mz_channel_comment()).
    # Requesting a scope during refresh() that this stored token was never
    # granted makes google-auth reject with invalid_scope and crash the whole
    # run -- confirmed root cause of the Jul 29 2026 MZ outage. Keep this list
    # narrow until MZ is re-authed with refresh_token_mz.py.
    creds = Credentials.from_authorized_user_file(
        str(token_path),
        ["https://www.googleapis.com/auth/youtube.upload",
         "https://www.googleapis.com/auth/youtube"]
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())

    yt = build("youtube", "v3", credentials=creds)

    # Safety check: verify token's channel identity matches MZ
    me = yt.channels().list(mine=True, part="id,snippet").execute()
    if not me.get("items"):
        raise RuntimeError("YouTube token returned no channel — bad OAuth?")
    channel_id = me["items"][0]["id"]
    # Log — don't hard-fail if MZ channel id isn't yet configured
    print(f"  🔑 Uploading as channel: {channel_id} ({me['items'][0]['snippet']['title']})")

    body = {
        "snippet": {
            "title":       title[:100],
            "description": description,
            "tags":        tags[:15],
            "categoryId":  "22",   # People & Blogs — matches MZ_Channel_Setup.md
        },
        "status": {
            "privacyStatus":           privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_path), resumable=True, chunksize=1024 * 1024 * 4)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = req.next_chunk()

    video_id = response["id"]
    video_url = f"https://youtu.be/{video_id}"

    # Optional: upload custom thumbnail
    if thumbnail_path and thumbnail_path.exists():
        try:
            yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))).execute()
            print(f"  🖼️  Custom thumbnail uploaded")
        except Exception as e:
            print(f"  ⚠️ Thumbnail upload failed (non-fatal): {e}")

    return video_url


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format",  choices=["A", "B", "C"],
                        help="Force a specific format (skip auto-rotation).")
    parser.add_argument("--topic",   help="Override topic string.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Render only, skip YouTube upload.")
    parser.add_argument("--unlisted", action="store_true",
                        help="Upload as unlisted (not public). Use for first routing test.")
    args = parser.parse_args()

    print(f"\n{'═' * 60}")
    print(f"  🎬 Minute Zero Auto-Post  |  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═' * 60}")

    # 1. Topic selection
    if args.topic:
        topic = args.topic
        format_tag = {"A": "one_bad_day", "B": "unknown_failure", "C": "near_death"}[args.format or "A"]
    else:
        if args.format:
            fmt = args.format
        else:
            now = dt.datetime.now(dt.timezone.utc)
            # Central Time is UTC-5 (CDT) or -6 (CST). Use -5 as conservative default for daylight savings.
            ct = now - dt.timedelta(hours=5)
            fmt = pick_format_for_slot(ct.weekday(), ct.hour)
            # Aug 29 2026: this fallback reads the clock at EXECUTION time, which
            # is only the intended slot if the runner started on time. It did not
            # between Aug 27-29. Scheduled runs now pass --format explicitly; if
            # we still land here on CI, say so instead of silently guessing.
            if os.getenv("GITHUB_ACTIONS") == "true":
                print(f"::warning::MZ format {fmt} was derived from the wall clock "
                      f"({ct:%Y-%m-%d %H:%M} CT), not from an explicit slot. If this "
                      f"run started late, the format may not match its cron.")
        topic, format_tag = pick_topic(fmt)

    print(f"\n📖 Format: {format_tag}")
    print(f"📖 Topic : {topic}")

    # 2. Generate script — with Format B fallback if primary format exhausts retries.
    # Format B (unknown_failure / US fraud stories) has been the most reliable generator,
    # so if Format A or C can't produce a valid script in 3 attempts we pivot to B
    # rather than skip entirely. This makes true skips nearly impossible.
    print(f"\n✍️  Generating v3 script (backend: {MODEL_BACKEND}) ...")
    def _mark_topic_used(t: str) -> None:
        """Add topic to dedup log so the same stubborn topic isn't retried next run."""
        log = _load_log()
        used = log.get("mz_topics_used", [])
        if t not in used:
            used.append(t)
            log["mz_topics_used"] = used
            _save_log(log)
            print(f"   📝 Marked skipped topic as used: {t[:60]}")

    # Aug 29 2026: a topic the generator REFUSES is a recoverable skip, but it
    # does not arrive as ValueError/TITLE_VALIDATION_SKIP. When both LLM backends
    # reject the topic itself ("Gate 1 failed; X is not a household name") the
    # raise is RuntimeError("Both LLM backends failed. ..."), which this handler
    # did not catch -- so _mark_topic_used() never ran, the topic stayed in the
    # pool to fail again forever, and the Format B fallback never fired. Match on
    # the REJECTION MARKER, not the exception class. A real infrastructure
    # failure (missing key, network down) carries no marker and still raises.
    _TOPIC_REJECTED = ("TITLE_VALIDATION_SKIP", "topic_rejected", "self-rejected")

    def _is_topic_rejection(msg: str) -> bool:
        return any(m in msg for m in _TOPIC_REJECTED)

    try:
        script_data = generate_script(topic, format_tag)
    except (ValueError, RuntimeError) as e:
        err = str(e)
        if not _is_topic_rejection(err):
            raise

        # Primary format failed — mark topic used and try Format B fallback
        # (skip fallback if we were already running Format B to avoid infinite loop)
        print(f"\n⚠️  Primary format ({format_tag}) exhausted retries: {err[22:120]}")
        _mark_topic_used(topic)

        if format_tag != "unknown_failure":
            print("   🔄 Falling back to Format B (unknown_failure) ...")
            try:
                fb_topic, fb_format_tag = pick_topic("B")
            except TopicBankExhausted as te:
                print(f"\n⏭️  SKIPPED — {te}")
                append_to_google_sheets(f"[SKIPPED] topic bank exhausted", "", format_tag)
                return 0
            print(f"   📖 Fallback topic: {fb_topic}")
            try:
                script_data = generate_script(fb_topic, fb_format_tag)
                format_tag = fb_format_tag
                topic = fb_topic
                print(f"   ✅ Fallback succeeded — posting Format B instead")
            except (ValueError, RuntimeError) as e2:
                err2 = str(e2)
                if _is_topic_rejection(err2):
                    _mark_topic_used(fb_topic)
                    print(f"\n⏭️  SKIPPED — both primary and fallback failed.")
                    append_to_google_sheets(
                        f"[SKIPPED] primary+fallback failed — {err[22:80]}", "", format_tag
                    )
                    return 0
                raise
        else:
            # Was already Format B — no further fallback
            print(f"\n⏭️  SKIPPED (Format B, no further fallback): {err[22:100]}")
            append_to_google_sheets(f"[SKIPPED] {err[22:100]}", "", format_tag)
            return 0
    print(f"  ✅ Title: {script_data['title']}")
    print(f"  ✅ Duration target: {script_data.get('target_duration_sec', '?')}s")
    # Hook rotation telemetry (v3 → v4): log each variant's style + validity.
    # A variant's `hook` may legitimately be null if the LLM couldn't generate
    # that style; we surface those so v4 weighting can trust the data.
    hooks = script_data.get("hooks", []) or []
    for i, h in enumerate(hooks):
        style = (h or {}).get("style", "?")
        text  = (h or {}).get("hook")
        status = "∅ null" if not text else f"{len(text)} chars"
        print(f"  ✅ Hook[{i}] {style}: {status}")
    if not any((h or {}).get("hook") for h in hooks):
        print("  ⚠️  All hook variants null — script body hook will still render, but v4 rotation data is empty")

    # 2b. Append spoken subscribe CTA (after validators — word band untouched)
    script_data, sub_cta_used = append_sub_cta(script_data, topic)

    # 3. Render
    print(f"\n🎥 Rendering video (clean master + variants) ...")
    from video_mz import render_video
    out_dir = MZ_OUTPUT_DIR / dt.date.today().isoformat()
    result = render_video(script_data, out_dir)
    print(f"  ✅ Master:    {result['master_path']}")
    print(f"  ✅ YT:        {result['yt_path']}")
    print(f"  ✅ TikTok:    {result['tt_path']}")
    print(f"  ✅ Instagram: {result['ig_path']}")
    print(f"  ✅ Thumb:     {result['thumb_path']}")

    if args.dry_run:
        print(f"\n⏹️  Dry run — skipping YouTube upload.")
        return 0

    # 4. Upload to YouTube
    print(f"\n📤 Uploading to YouTube ...")
    hashtags = script_data.get("hashtags", "").strip()
    tags = [h.lstrip("#") for h in hashtags.split() if h.startswith("#")]
    # Subscribe line sits above the hashtags — visible in the collapsed
    # description on mobile, where most Shorts viewers are. Added Aug 2 2026.
    description = (
        f"{script_data.get('description', '')}\n\n"
        f"\U0001f4c9 A new business collapse every day — subscribe to Minute Zero.\n\n"
        f"{hashtags}"
    ).strip()

    # ---- Pre-upload QC gate (added Aug 23 2026) -------------------------
    # Blocks unambiguously broken renders. "The Tweet That Killed Vine"
    # (470 views @ 4% retention) and the 40s Western Union render are the
    # two that motivated this. See render_qc.py.
    try:
        from render_qc import enforce as _qc_enforce, QCError as _QCError
    except ImportError as _qc_imp_err:
        print(f"::error::QC gate unavailable ({_qc_imp_err}) -- refusing to upload unchecked.")
        print("   Set QC_DISABLE=1 to bypass deliberately.")
        sys.exit(1)
    else:
        try:
            _qc_enforce(Path(result["yt_path"]), channel="mz", kind="short")
        except _QCError as _qc_err:
            print(f"\n{_qc_err}")
            print("   Not uploading. Re-render and try again.")
            sys.exit(1)

    video_url = upload_to_youtube(
        Path(result["yt_path"]),
        title=script_data["title"],
        description=description,
        tags=tags,
        thumbnail_path=Path(result["thumb_path"]),
        privacy_status="unlisted" if args.unlisted else "public",
    )
    print(f"  ✅ Posted ({'unlisted' if args.unlisted else 'public'}): {video_url}")

    # Post pinned comment — subscribe ask + engagement question (pin in Studio)
    post_mz_channel_comment(video_url.split("/")[-1], topic)

    # 5. Log
    mark_mz_posted(topic, script_data["title"], video_url, format_tag)
    append_to_google_sheets(script_data["title"], video_url, format_tag)

    # 6. Post TikTok variant (if TIKTOK_ACCESS_TOKEN is set)
    tt_path = Path(result["tt_path"])
    tiktok_publish_id = None
    if os.environ.get("TIKTOK_ACCESS_TOKEN") or (BASE_DIR / "tiktok_token.json").exists():
        print(f"\n📱 Posting TikTok variant ...")
        try:
            from tiktok_post import post_to_tiktok, load_access_token
            tt_token = load_access_token()
            tt_title = script_data["title"]
            tiktok_publish_id = post_to_tiktok(tt_path, tt_title, tt_token)
            print(f"  ✅ TikTok posted — Publish ID: {tiktok_publish_id}")
        except Exception as e:
            print(f"  ⚠️  TikTok post failed (non-fatal): {str(e)[:200]}")
    else:
        print(f"\n⏭️  Skipping TikTok post (TIKTOK_ACCESS_TOKEN not set)")

    # 7. Trigger file for traceability (matches TMF/BSG pattern)
    trigger_path = BASE_DIR / f"auto_trigger_mz_{time.strftime('%Y%m%d_%H%M')}.json"
    trigger_path.write_text(json.dumps({
        "channel":     "mz",
        "format_tag":  format_tag,
        "topic":       topic,
        "title":       script_data["title"],
        "video_url":   video_url,
        "master_path": result["master_path"],
        "tt_path":          result["tt_path"],
        "tiktok_publish_id": tiktok_publish_id,   # None if not posted
        "ig_path":     result["ig_path"],    # Instagram variant — future
        "thumb_path":  result["thumb_path"],
        "posted_at":   time.strftime("%Y-%m-%d %H:%M:%S"),
    }, indent=2))
    print(f"  📄 Trigger file: {trigger_path.name}")

    print(f"\n{'═' * 60}")
    print(f"  🎉 SUCCESS — Minute Zero")
    print(f"  Topic : {topic}")
    print(f"  Title : {script_data['title']}")
    print(f"  URL   : {video_url}")
    print(f"{'═' * 60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
