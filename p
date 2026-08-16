#!/data/data/com.termux/files/usr/bin/sh
set -eu

app_dir="$HOME/phone_guardian"
boot_dir="$HOME/.termux/boot"

pkg install -y python
mkdir -p "$app_dir" "$boot_dir" "$app_dir/logs" "$app_dir/state"
curl -fsSL "https://raw.githubusercontent.com/giudittamcnary07-droid/reports/main/maps_resolver.py" -o "$app_dir/maps_resolver.py"
python -m py_compile "$app_dir/maps_resolver.py"

cat > "$boot_dir/start-maps-resolver.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
pkill -f '[m]aps_resolver.py' 2>/dev/null || true
nohup python "$HOME/phone_guardian/maps_resolver.py" >>"$HOME/phone_guardian/maps_resolver.log" 2>&1 &
EOF

chmod 700 "$boot_dir/start-maps-resolver.sh"
sh "$boot_dir/start-maps-resolver.sh"
sleep 2
curl -fsS http://127.0.0.1:8767/health
printf '\nBOOTSTRAP_OK\n'
