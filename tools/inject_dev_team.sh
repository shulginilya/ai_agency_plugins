cd ../
PY=$(command -v python3 || command -v python)
for p in developer scrum-master designer qa devops; do
  "$PY" -m tools.apkit install "$p" --target claude-code --scope user
done