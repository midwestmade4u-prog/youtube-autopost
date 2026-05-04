# YouTube Automation Monitoring Checklist

**Start Date:** April 16, 2026 (Evening)  
**Goal:** Verify both workflows run automatically without manual intervention

---

## TODAY (April 16, 2026)

### 7:00 PM CST — Bible Story Garden (BSG) Posts
**Time to check:** 7:05 PM CST

- [ ] GitHub Actions → See `bsg-autopost` workflow running
- [ ] BSG YouTube channel → New video published
- [ ] Workflow status: ✅ Success or ❌ Failed?
- [ ] Notes: _______________________________________________

### 9:00 PM CST — The Mind Files (TMF) Posts
**Time to check:** 9:05 PM CST

- [ ] GitHub Actions → See `tmf-autopost` workflow running
- [ ] TMF YouTube channel → New video published
- [ ] Workflow status: ✅ Success or ❌ Failed?
- [ ] Notes: _______________________________________________

---

## TOMORROW (April 17, 2026)

### 7:00 AM CST — The Mind Files (TMF) Posts
**Time to check:** 7:05 AM CST

- [ ] GitHub Actions → See `tmf-autopost` workflow running
- [ ] TMF YouTube channel → New video published
- [ ] Notes: _______________________________________________

### 12:00 PM CST — Both Channels Post
**Time to check:** 12:05 PM CST

- [ ] GitHub Actions → See BOTH workflows running
- [ ] BSG YouTube → New video
- [ ] TMF YouTube → New video (different from 7 AM post)
- [ ] Notes: _______________________________________________

### 7:00 PM CST — Bible Story Garden (BSG) Posts
**Time to check:** 7:05 PM CST

- [ ] GitHub Actions → See `bsg-autopost` workflow running
- [ ] BSG YouTube channel → New video published
- [ ] Notes: _______________________________________________

### 9:00 PM CST — The Mind Files (TMF) Posts
**Time to check:** 9:05 PM CST

- [ ] GitHub Actions → See `tmf-autopost` workflow running
- [ ] TMF YouTube channel → New video published
- [ ] Notes: _______________________________________________

---

## How to Check GitHub Actions

1. Go to: https://github.com/midwestmade4u-prog/youtube-autopost
2. Click **"Actions"** tab
3. Look for the workflow that should be running at that time
4. Click it to see detailed logs

**What success looks like:**
- Green checkmark ✅ next to workflow name
- Status shows "completed successfully"
- Logs show "Auto-post videos" commit message

**What failure looks like:**
- Red X ❌ next to workflow name
- Error message in logs
- Check the error details to understand what failed

---

## Quick Reference: Scheduled Times

| Time | Channel | Frequency |
|------|---------|-----------|
| 7:00 AM CST | TMF | Daily |
| 12:00 PM CST | BSG + TMF | Daily |
| 7:00 PM CST | BSG | Daily |
| 9:00 PM CST | TMF | Daily |

---

## If Something Fails

**Document it:** Note the error in this checklist or the Google Sheets log  
**Check:** Auto_post.py logs in GitHub Actions artifacts  
**Common issues:**
- API key expired or incorrect
- YouTube token missing/invalid
- Network timeout
- Script dependency missing

Let me know immediately if any workflows fail!
