# /setup

Set up persistent memory on this machine - the driver, a local MongoDB in Docker, the indexes and the connection string. Safe to run again.

Set up memory: $ARGUMENTS

Run `python "/home/runner/work/ai_agency_plugins/ai_agency_plugins/plugins/memory/skills/memory-keeping/scripts/setup_db.py" $ARGUMENTS` with a
timeout of 10 minutes: the first run downloads the MongoDB image.

- Exit 0: report what it changed, or that nothing changed. When something
  changed, tell the user to restart the session (or run `/reload-plugins`).
- Exit 1: report the message as it is and stop. Never delete a container,
  volume or config file to get past it, and never run `sudo`: give the user the
  command to run.

Never read, print or copy the config file: it holds the database password.
