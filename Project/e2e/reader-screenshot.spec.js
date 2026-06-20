const { test, expect } = require('@playwright/test');
const path = require('path');

test('capture reader screenshots', async ({ page }) => {
  // Navigate to book reader page for digital book 38
  await page.goto('/books/38/read/');
  
  // Wait for content to render
  await page.waitForSelector('#pageContent p');
  
  // Define artifact path
  const artifactDir = path.join('test-results', 'reader-screenshots');
  
  // 1. Take screenshot of default page (Light / Sepia default)
  await page.screenshot({ path: path.join(artifactDir, 'reader_default.png') });
  
  // 2. Add bookmark (while panel is closed)
  await page.mouse.move(40, 40);
  await page.locator('#bookmarkBtn').dispatchEvent('click');
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(artifactDir, 'reader_bookmarked.png') });
  
  // 3. Open customization drawer
  await page.mouse.move(40, 40);
  await page.locator('#togglePanelBtn').dispatchEvent('click');
  await page.waitForTimeout(400); // wait for slider transition
  
  // 4. Choose Cozy Sepia theme
  await page.locator('.reader-theme-btn[data-theme-choice="sepia"]').dispatchEvent('click');
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(artifactDir, 'reader_sepia.png') });
  
  // 5. Choose OLED Dark theme and close drawer
  await page.locator('.reader-theme-btn[data-theme-choice="dark"]').dispatchEvent('click');
  await page.locator('#closePanelBtn').dispatchEvent('click');
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(artifactDir, 'reader_dark.png') });
});
