const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const screenshotDir = path.resolve(__dirname, '../../docs/screenshots');

test.skip(process.env.BOOKIE_SCREENSHOTS !== '1', 'Run `npm run screenshots` to capture portfolio screenshots.');

async function waitForStablePage(page) {
  await page.waitForLoadState('domcontentloaded');
  if (await page.locator('#home-loader').count()) {
    await page.waitForFunction(() => {
      const loader = document.querySelector('#home-loader');
      return !loader || loader.classList.contains('hidden');
    }, null, { timeout: 6_000 }).catch(async () => {
      await page.locator('#home-loader').evaluate((loader) => loader.classList.add('hidden')).catch(() => {});
    });
  }
  await page.waitForTimeout(700);
}

async function capture(page, filename) {
  await waitForStablePage(page);
  await page.screenshot({
    path: path.join(screenshotDir, filename),
    fullPage: false,
  });
}

async function loginAs(page, username, password) {
  await page.goto('/login/');
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="password"]').fill(password);
  await page.locator('form[action="/login/"] button[type="submit"]').click();
  await expect(page).toHaveURL(/\/$/);
}

async function addFirstAvailableBookToCart(page) {
  await page.goto('/books/');
  const firstAddButton = page.locator('.ajax-add-cart').first();
  await expect(firstAddButton).toBeVisible();
  await firstAddButton.click();
  await expect(page.locator('#cart-badge')).toHaveText(/[1-9]\d*/);
}

async function prepareCheckout(page, paymentMethod = 'cod') {
  await addFirstAvailableBookToCart(page);
  await page.goto('/checkout/');
  await page.locator(`#pay_${paymentMethod}`).check();
  await page.locator('textarea[name="shipping_address"]').fill('12 Nguyen Trai, Da Nang');
}

async function openReader(page) {
  await page.goto('/ebooks/');
  const firstReadLink = page.locator('a[href*="/read/"]').first();
  await expect(firstReadLink).toBeVisible();
  await firstReadLink.click();
  await expect(page).toHaveURL(/\/books\/\d+\/read\/$/);
}

async function mockChatbot(page) {
  await page.route('**/api/v1/chatbot/stream/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/x-ndjson',
      body: [
        JSON.stringify({ type: 'start' }),
        JSON.stringify({ type: 'delta', content: 'Bookie recommends a catalog-backed demo title for this portfolio walkthrough.' }),
        JSON.stringify({
          type: 'final',
          payload: {
            type: 'text',
            text: 'Bookie recommends a catalog-backed demo title for this portfolio walkthrough.',
          },
        }),
      ].join('\n') + '\n',
    });
  });
}

test.describe('portfolio screenshots', () => {
  test('capture desktop and mobile screenshots', async ({ page }, testInfo) => {
    fs.mkdirSync(screenshotDir, { recursive: true });
    await mockChatbot(page);

    const isMobile = testInfo.project.name.includes('mobile');

    if (isMobile) {
      await page.goto('/');
      await capture(page, 'mobile-01-home.png');

      await page.goto('/books/');
      await capture(page, 'mobile-02-catalog.png');

      await loginAs(page, 'demo', 'demo123');
      await prepareCheckout(page, 'cod');
      await capture(page, 'mobile-03-checkout.png');

      await openReader(page);
      await capture(page, 'mobile-04-reader.png');
      return;
    }

    await page.goto('/');
    await capture(page, 'desktop-01-home.png');

    await page.goto('/books/');
    await capture(page, 'desktop-02-catalog.png');

    await page.locator('.card-book a[href^="/books/"]').first().click();
    await expect(page).toHaveURL(/\/books\/\d+\/$/);
    await capture(page, 'desktop-03-book-detail.png');

    await loginAs(page, 'demo', 'demo123');
    await addFirstAvailableBookToCart(page);
    await page.goto('/cart/');
    await capture(page, 'desktop-04-cart.png');

    await page.goto('/checkout/');
    await page.locator('#pay_momo').check();
    await page.locator('textarea[name="shipping_address"]').fill('12 Nguyen Trai, Da Nang');
    await capture(page, 'desktop-05-checkout.png');

    await page.locator('button[form="checkout-form"]:visible, #checkout-form button[type="submit"]:visible').first().click();
    await expect(page).toHaveURL(/\/orders\/\d+\/payment\/$/);
    await capture(page, 'desktop-06-payment-momo.png');

    await page.locator('form[action*="/payment/confirm/"] button[type="submit"]').click();
    await expect(page).toHaveURL(/\/orders\/\d+\/$/);
    await capture(page, 'desktop-07-order-detail.png');

    await page.context().clearCookies();
    await loginAs(page, 'admin', 'admin123');
    await page.goto('/dashboard/');
    await capture(page, 'desktop-08-dashboard.png');

    await openReader(page);
    await capture(page, 'desktop-09-reader.png');

    await page.goto('/');
    await page.locator('#chatBubble').dispatchEvent('click');
    await expect(page.locator('#chatWindow')).toHaveClass(/show/);
    await page.locator('#chatInput').fill('Suggest a book for me');
    await page.locator('#chatInput').press('Enter');
    await expect(page.locator('#chatBody')).toContainText('Bookie recommends');
    await capture(page, 'desktop-10-chatbot.png');
  });
});
