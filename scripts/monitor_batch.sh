#!/usr/bin/env bash
# Stage 11 batch monitor. Prints one line per event worth acting on, and nothing else:
#   - progress, failure and completion lines from the batch log (never per-claim decision lines)
#   - the runner process dying without BATCH COMPLETE, and coming back (after a restart the new pid is
#     read from the status file, so a restarted runner is picked up without re-arming this monitor)
#   - a stale heartbeat (machine asleep, crashed, or runner hung)
#   - the laptop moving between charger and battery, and low battery
# Exits 0 when BATCH COMPLETE appears in the log.
#
# It does NOT survive a reboot or the end of the session that started it. Re-arm it with
# (Git Bash, from anywhere):
#   bash "/c/Users/HP/Desktop/AI Builders Hackathon/scripts/monitor_batch.sh"
# In Claude Code, ask for a persistent Monitor running that same command.
#
# Settings for testing: MONITOR_DATA_DIR (folder with the log and status file), MONITOR_INTERVAL
# (seconds between checks, default 60), MONITOR_POWER_EVERY (check power every N checks; 0 = never).

DATA_DIR="${MONITOR_DATA_DIR:-/c/Users/HP/Desktop/AI Builders Hackathon/backend/data}"
INTERVAL="${MONITOR_INTERVAL:-60}"
POWER_EVERY="${MONITOR_POWER_EVERY:-5}"
STALE_SECONDS=900
LOG="$DATA_DIR/stage11_batch_output.log"
STATUS="$DATA_DIR/stage11_batch_status.json"

seen=$(wc -l < "$LOG" 2>/dev/null || echo 0)
stale_alerted=""
dead_alerted=""
last_pid=""
last_power=""
batt_alerted=100
tick=0
echo "MONITOR armed at $(date -u '+%H:%M:%S') UTC; runner pid read from the status file every ${INTERVAL}s"

while true; do
  # New log lines: relay only progress, failures, completion and crashes.
  total=$(wc -l < "$LOG" 2>/dev/null || echo "$seen")
  if [ "$total" -gt "$seen" ]; then
    sed -n "$((seen + 1)),${total}p" "$LOG" | grep -E "PROGRESS|failure [0-9]|giving up|BATCH COMPLETE|Traceback|STOP" || true
    seen=$total
  fi
  if grep -q "BATCH COMPLETE" "$LOG" 2>/dev/null; then
    echo "MONITOR: BATCH COMPLETE is in the log; monitor exiting"
    exit 0
  fi

  # Runner process: the pid comes from the status file each time, so a restart is followed automatically.
  pid=$(grep -o '"pid": *[0-9]*' "$STATUS" 2>/dev/null | grep -o '[0-9]*$')
  if [ -n "$pid" ]; then
    if tasklist //FI "PID eq $pid" //NH 2>/dev/null | grep -q " $pid "; then
      if [ -n "$dead_alerted" ] || { [ -n "$last_pid" ] && [ "$pid" != "$last_pid" ]; }; then
        echo "MONITOR: batch runner is running (pid $pid)"
      fi
      dead_alerted=""
    elif [ -z "$dead_alerted" ]; then
      echo "MONITOR ALERT: batch runner pid $pid is not running and BATCH COMPLETE was not logged (restart: docs/RUNBOOK.md step 0)"
      dead_alerted=1
    fi
    last_pid=$pid
  fi

  # Heartbeat age.
  updated=$(grep -o '"updated_at": *"[^"]*"' "$STATUS" 2>/dev/null | sed -E 's/.*"([^"]+)"$/\1/')
  if [ -n "$updated" ]; then
    updated_epoch=$(date -u -d "$updated" +%s 2>/dev/null)
    if [ -n "$updated_epoch" ]; then
      age=$(( $(date -u +%s) - updated_epoch ))
      if [ "$age" -gt "$STALE_SECONDS" ] && [ -z "$stale_alerted" ]; then
        echo "MONITOR ALERT: batch heartbeat is $((age / 60)) minutes old (machine asleep, crashed or runner hung?)"
        stale_alerted=1
      elif [ "$age" -le "$STALE_SECONDS" ] && [ -n "$stale_alerted" ]; then
        echo "MONITOR: batch heartbeat is fresh again"
        stale_alerted=""
      fi
    fi
  fi

  # Power: charger/battery changes and low battery.
  if [ "$POWER_EVERY" -gt 0 ] && [ $((tick % POWER_EVERY)) -eq 0 ]; then
    power=$(powershell.exe -NoProfile -Command '$b = Get-CimInstance Win32_Battery; "$([int]($b.BatteryStatus -eq 2)) $($b.EstimatedChargeRemaining)"' 2>/dev/null | tr -d '\r')
    on_ac=${power%% *}; charge=${power##* }
    if [ -n "$on_ac" ] && [ "$on_ac" != "$last_power" ]; then
      if [ -n "$last_power" ] || [ "$on_ac" = "0" ]; then
        if [ "$on_ac" = "1" ]; then echo "MONITOR: laptop is on AC power (battery ${charge}%)"
        else echo "MONITOR ALERT: laptop is on battery (${charge}%); plug in to protect the batch"; fi
      fi
      last_power=$on_ac
    fi
    if [ "$on_ac" = "0" ] && [ -n "$charge" ]; then
      for level in 20 10 5; do
        if [ "$charge" -le "$level" ] && [ "$batt_alerted" -gt "$level" ]; then
          echo "MONITOR ALERT: battery at ${charge}% and not charging; the batch stops if the laptop shuts down"
          batt_alerted=$level
        fi
      done
    fi
    [ "$on_ac" = "1" ] && batt_alerted=100
  fi

  tick=$((tick + 1))
  sleep "$INTERVAL"
done
