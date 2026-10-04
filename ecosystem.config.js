// Konfigurasi PM2 untuk menjalankan Auto Discord Poster 24/7.
// PM2 dipakai untuk auto-restart saat crash + auto-start saat server reboot.
//
// Cara pakai di server Ubuntu:
//   pm2 start ecosystem.config.js
//   pm2 save
//   pm2 startup            # lalu jalankan perintah yang ditampilkan
//
// Catatan: sesuaikan "cwd" dan "interpreter" dengan lokasi project di server Anda.
module.exports = {
  apps: [
    {
      name: "auto-discord-poster",
      script: "app.py",
      // Gunakan python dari virtualenv agar dependency konsisten.
      // Jika tidak memakai venv, ganti menjadi "python3".
      interpreter: "./.venv/bin/python",
      cwd: __dirname,
      autorestart: true,
      watch: false,
      max_restarts: 30,
      min_uptime: "10s",
      restart_delay: 5000,
      max_memory_restart: "350M",
      kill_timeout: 8000,
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
  ],
};
