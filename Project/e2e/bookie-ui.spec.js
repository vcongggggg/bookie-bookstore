const { test, expect } = require('@playwright/test');

function attachUiDiagnostics(page) {
  const consoleErrors = [];
  const failedRequests = [];

  page.on('console', (message) => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text());
    }
  });

  page.on('response', (response) => {
    const status = response.status();
    const url = response.url();
    if (status >= 500 && !url.includes('/api/v1/chatbot/')) {
      failedRequests.push(`${status} ${url}`);
    }
  });

  page.on('pageerror', (error) => {
    consoleErrors.push(error.message);
  });

  return {
    assertClean() {
      expect(consoleErrors, `Console/page errors:\n${consoleErrors.join('\n')}`).toEqual([]);
      expect(failedRequests, `5xx responses:\n${failedRequests.join('\n')}`).toEqual([]);
    },
  };
}

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => ({
    viewport: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth,
  }));

  expect(
    Math.max(overflow.documentWidth, overflow.bodyWidth),
    `Horizontal overflow: viewport=${overflow.viewport}, document=${overflow.documentWidth}, body=${overflow.bodyWidth}`,
  ).toBeLessThanOrEqual(overflow.viewport + 2);
}

async function loginAsDemo(page) {
  await page.goto('/login/');
  await page.locator('input[name="username"]').fill('demo');
  await page.locator('input[name="password"]').fill('demo123');
  await page.locator('form[action="/login/"] button[type="submit"]').click();
  await expect(page).toHaveURL(/\/$/);
}

test.describe('Bookie UI smoke tests', () => {
  test('public pages render cleanly without horizontal overflow', async ({ page }) => {
    const diagnostics = attachUiDiagnostics(page);
    const publicPages = ['/', '/books/', '/categories/', '/about/', '/contact/'];

    for (const path of publicPages) {
      await page.goto(path);
      await expect(page.locator('body')).toBeVisible();
      await expect(page.locator('#chatBubble')).toBeVisible();
      await expectNoHorizontalOverflow(page);
    }

    diagnostics.assertClean();
  });

  test('demo user can add a book to cart and reach checkout', async ({ page }) => {
    const diagnostics = attachUiDiagnostics(page);

    await loginAsDemo(page);
    await page.goto('/books/');
    const firstAddButton = page.locator('.ajax-add-cart').first();
    await expect(firstAddButton).toBeVisible();
    await firstAddButton.click();

    await expect(page.locator('#cart-badge')).toHaveText(/[1-9]\d*/);
    await page.goto('/cart/');
    await expect(page.locator('#cart-form')).toBeVisible();
    await expect(page.locator('input[type="number"]').first()).toHaveValue(/[1-9]\d*/);

    await page.locator('a[href="/checkout/"]').click();
    await expect(page).toHaveURL(/\/checkout\/$/);
    await expect(page.locator('#checkout-form')).toBeVisible();
    await page.locator('textarea[name="shipping_address"]').fill('12 Nguyen Trai, Da Nang');
    await expectNoHorizontalOverflow(page);

    diagnostics.assertClean();
  });

  test('chat widget opens and renders a mocked bot reply', async ({ page }) => {
    const diagnostics = attachUiDiagnostics(page);

    await page.route('**/api/v1/chatbot/stream/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/x-ndjson',
        body: [
          JSON.stringify({ type: 'start' }),
          JSON.stringify({ type: 'delta', content: 'Bookie test reply' }),
          JSON.stringify({ type: 'final', payload: { text: 'Bookie test reply', type: 'text' } }),
        ].join('\n') + '\n',
      });
    });

    await page.goto('/');
    await page.locator('#chatBubble').dispatchEvent('click');
    await expect(page.locator('#chatWindow')).toHaveClass(/show/);
    await page.locator('#chatInput').fill('Xin chao Bookie');
    await page.locator('#chatInput').press('Enter');

    await expect(page.locator('#chatBody')).toContainText('Xin chao Bookie');
    await expect(page.locator('#chatBody')).toContainText('Bookie test reply');
    await expectNoHorizontalOverflow(page);

    diagnostics.assertClean();
  });
});
