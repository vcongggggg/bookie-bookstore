const { spawnSync } = require('child_process');
const path = require('path');

const projectRoot = path.resolve(__dirname, '..');
const playwrightBin = path.join(
  projectRoot,
  'node_modules',
  '.bin',
  process.platform === 'win32' ? 'playwright.cmd' : 'playwright',
);

const result = spawnSync(
  playwrightBin,
  ['test', 'e2e/screenshots.spec.js'],
  {
    cwd: projectRoot,
    stdio: 'inherit',
    shell: process.platform === 'win32',
    env: {
      ...process.env,
      BOOKIE_SCREENSHOTS: '1',
    },
  },
);

if (result.error) {
  console.error(result.error);
}

process.exit(result.status ?? 1);
