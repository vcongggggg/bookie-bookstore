const { test, expect } = require('@playwright/test');
const path = require('path');

test('capture reader screenshots', async ({ page }) => {
  // Set viewport for standard laptop screen
  await page.setViewportSize({ width: 1280, height: 800 });

  // Navigate to book reader page for digital book 38
  await page.goto('http://127.0.0.1:8000/books/38/read/');
  
  // Wait for content to render
  await page.waitForSelector('#pageContent p');
  
  // Define artifact path
  const artifactDir = 'C:/Users/ADMIN/.gemini/antigravity-ide/brain/dfe16a50-066e-4657-8f17-8bc53063774b';
  
  // 1. Take screenshot of default page (Light / Sepia default)
  await page.screenshot({ path: path.join(artifactDir, 'reader_default.png') });
  
  // 2. Add bookmark (while panel is closed)
  await page.click('#bookmarkBtn');
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(artifactDir, 'reader_bookmarked.png') });
  
  // 3. Open customization drawer
  await page.click('#togglePanelBtn');
  await page.waitForTimeout(400); // wait for slider transition
  
  // 4. Choose Cozy Sepia theme
  await page.click('.reader-theme-btn[data-theme-choice="sepia"]');
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(artifactDir, 'reader_sepia.png') });
  
  // 5. Choose OLED Dark theme and close drawer
  await page.click('.reader-theme-btn[data-theme-choice="dark"]');
  await page.click('#closePanelBtn');
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(artifactDir, 'reader_dark.png') });
});
