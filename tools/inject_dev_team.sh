cd ../
for p in developer debugger code-review scrum-master; do
  (python3 || python) -m tools.apkit install "$p" --target claude-code --scope user
done