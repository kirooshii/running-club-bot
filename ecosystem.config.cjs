// PM2 config for the bot.
// Start:   pm2 start ecosystem.config.cjs
// Logs:    pm2 logs lada-bot
// Restart: pm2 restart lada-bot
//
// IMPORTANT:
//  - script points at the venv python and runs `python -m bot` (needed for
//    package-relative imports; do NOT run bot/__main__.py directly).
//  - instances MUST stay 1. Telegram allows only one connection per bot token;
//    running 2+ copies causes 409 Conflict and duplicate messages.
module.exports = {
  apps: [
    {
      name: "lada-bot",
      cwd: __dirname,
      script: ".venv/bin/python",
      args: "-m bot",
      interpreter: "none",
      exec_mode: "fork",
      instances: 1,
      autorestart: true,
      max_restarts: 20,
      exp_backoff_restart_delay: 1000,
      max_memory_restart: "300M",
      env: {
        PYTHONUNBUFFERED: "1", // flush logs immediately so `pm2 logs` is live
      },
    },
  ],
};
