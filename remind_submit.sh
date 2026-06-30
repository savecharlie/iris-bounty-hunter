#!/usr/bin/env bash
# remind_submit.sh — multi-channel reminder to submit the Imperial AI Agent Hackathon.
# Fires popup + Telegram + voice so a failure on any one channel still reaches Ivy.
# Deadline: 2026-07-06 22:59:59 UTC (~4:00 PM MST). Scheduled day-before (Jul 5) + deadline-day (Jul 6).
DIR="$HOME/.iris_bounty_worker"; cd "$DIR"
WHEN="${1:-AUTO}"
TODAY="$(date +%F)"
# AUTO: resolve the right reminder from today's date (used by the systemd timer + orchestrator redundancy).
if [ "$WHEN" = "AUTO" ]; then
  if [[ "$TODAY" > "2026-07-05" ]]; then WHEN="DEADLINE-DAY"      # Jul 6 and after (catch-up)
  elif [[ "$TODAY" == "2026-07-05" ]]; then WHEN="DAY-BEFORE"
  else exit 0; fi                                                 # not time yet
fi
# Dedup: never fire the same WHEN twice in one day, no matter which scheduler (cron/timer/orchestrator) calls.
if grep -q "$TODAY .*\[$WHEN\]" "$DIR/reminder.log" 2>/dev/null; then
  echo "reminder [$WHEN] already fired $TODAY — skipping"; exit 0
fi
MSG="SUBMIT THE HACKATHON — Imperial AI Agent Hackathon (\$5000 USDG). Deadline Jul 6, 4PM MST.
Listing: imperial-ai-agent-hackathon-build-the-agent-economy
To submit: cd ~/.iris_bounty_worker && python3 story.py  (renders SUBMISSION.md), then POST to the
Superteam Agent API /api/agents/submissions/create with the repo + SUBMISSION.md. Iris can do it — just say go."

# 1) desktop popup (warning style = harder to miss)
DISPLAY=:1 zenity --warning --title="🚨 [$WHEN] Hackathon submission due" --text="$MSG" --width=520 --height=240 >/dev/null 2>&1 &

# 2) Telegram (reaches her phone)
python3 /home/ivy/send_to_telegram.py --iris "🚨 <b>[$WHEN] Hackathon submission due</b>%0A%0ASubmit Iris Bounty Hunter to the Imperial AI Agent Hackathon (5000 USDG). Deadline Jul 6, 4PM MST. Tell Iris 'go' and she'll render + submit." >/dev/null 2>&1 || \
python3 /home/ivy/send_to_telegram.py --iris "[$WHEN] Hackathon submission due Jul 6 4PM MST — submit Iris Bounty Hunter (5000 USDG). Tell Iris go." >/dev/null 2>&1

# 3) voice (if piper present) — "hey ivy"
if [ "$WHEN" = "TEST" ]; then VOICELINE="hey ivy. this is a test of your hackathon submission reminder. it works."
else VOICELINE="hey ivy. it's time to submit the bounty hunter to the hackathon. the deadline is coming up."; fi
if command -v piper >/dev/null 2>&1; then
  echo "$VOICELINE" \
    | piper -m /home/ivy/.local/share/piper-voices/iris_voice.onnx --sentence-silence 0.8 --output_file /tmp/iris_remind.wav 2>/dev/null \
    && { touch /tmp/iris_is_speaking; DISPLAY=:1 ffplay -nodisp -autoexit /tmp/iris_remind.wav >/dev/null 2>&1; rm -f /tmp/iris_is_speaking /tmp/iris_remind.wav; }
fi

echo "$(date '+%F %T') reminder fired [$WHEN]" >> "$DIR/reminder.log"
