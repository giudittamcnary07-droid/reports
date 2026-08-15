#!/data/data/com.termux/files/usr/bin/sh
set -eu

task_dir="$HOME/phone_guardian"
boot_dir="$HOME/.termux/boot"
resolver="$task_dir/maps_resolver.py"
boot_script="$boot_dir/start-maps-resolver.sh"

mkdir -p "$task_dir" "$boot_dir"
curl -fsSL "https://raw.githubusercontent.com/giudittamcnary07-droid/reports/main/maps_resolver.py" -o "$resolver.new"
python -m py_compile "$resolver.new"
if [ -f "$resolver" ]; then
  cp -f "$resolver" "$resolver.bak"
fi
mv -f "$resolver.new" "$resolver"

cat > "$boot_script" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
pkill -f '[m]aps_resolver.py' 2>/dev/null || true
nohup python "$HOME/phone_guardian/maps_resolver.py" >>"$HOME/phone_guardian/maps_resolver.log" 2>&1 &
EOF
chmod 700 "$boot_script"

pkill -f '[m]aps_resolver.py' 2>/dev/null || true
nohup python "$resolver" >>"$task_dir/maps_resolver.log" 2>&1 &
sleep 1
curl -fsS "http://127.0.0.1:8767/health"
printf '\nINSTALL_OK\n'
