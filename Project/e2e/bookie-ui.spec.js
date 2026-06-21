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

async function loginAs(page, username, password) {
  await page.goto('/login/');
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="password"]').fill(password);
  await page.locator('form[action="/login/"] button[type="submit"]').click();
  await expect(page).toHaveURL(/\/$/);
}

async function loginAsDemo(page) {
  await loginAs(page, 'demo', 'demo123');
}

async function addFirstAvailableBookToCart(page) {
  await page.goto('/books/');
  const firstAddButton = page.locator('.ajax-add-cart').first();
  await expect(firstAddButton).toBeVisible();
  await firstAddButton.click();
  await expect(page.locator('#cart-badge')).toHaveText(/[1-9]\d*/);
}

async function submitCheckout(page, { paymentMethod = 'cod', address = '12 Nguyen Trai, Da Nang' } = {}) {
  await page.goto('/checkout/');
  await expect(page.locator('#checkout-form')).toBeVisible();
  await page.locator(`#pay_${paymentMethod}`).check();
  await page.locator('textarea[name="shipping_address"]').fill(address);
  await expectNoHorizontalOverflow(page);
  await page.locator('button[form="checkout-form"]:visible, #checkout-form button[type="submit"]:visible').first().click();
}

function extractOrderIdFromUrl(url) {
  const match = url.match(/\/orders\/(\d+)\//);
  if (!match) throw new Error(`Could not extract order id from URL: ${url}`);
  return match[1];
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
    await expectNoHorizontalOverflow(page);

    await page.locator('a[href="/checkout/"]').click();
    await expect(page).toHaveURL(/\/checkout\/$/);
    await expect(page.locator('#checkout-form')).toBeVisible();
    await page.locator('textarea[name="shipping_address"]').fill('12 Nguyen Trai, Da Nang');
    await expectNoHorizontalOverflow(page);

    diagnostics.assertClean();
  });

  test('demo user can complete COD checkout and view order detail', async ({ page }) => {
    const diagnostics = attachUiDiagnostics(page);

    await loginAsDemo(page);
    await addFirstAvailableBookToCart(page);
    await submitCheckout(page, { paymentMethod: 'cod' });

    await expect(page).toHaveURL(/\/orders\/\d+\/$/);
    const orderId = extractOrderIdFromUrl(page.url());
    await expect(page.locator('body')).toContainText(`#${orderId}`);
    await expectNoHorizontalOverflow(page);

    const response = await page.request.get(`/api/v1/orders/${orderId}/`);
    expect(response.ok()).toBeTruthy();
    const order = await response.json();
    expect(order.payment_method).toBe('cod');
    expect(order.payment_status).not.toBe('paid');

    diagnostics.assertClean();
  });

  test('demo user can complete simulated Momo payment flow', async ({ page }) => {
    const diagnostics = attachUiDiagnostics(page);

    await loginAsDemo(page);
    await addFirstAvailableBookToCart(page);
    await submitCheckout(page, { paymentMethod: 'momo', address: '34 Bach Dang, Da Nang' });

    await expect(page).toHaveURL(/\/orders\/\d+\/payment\/$/);
    await expect(page.locator('body')).toContainText('Simulated Momo payment');
    await expect(page.locator('img[src*="/static/img/payments/qr-momo-mock.svg"]')).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.locator('form[action*="/payment/confirm/"] button[type="submit"]').click();
    await expect(page).toHaveURL(/\/orders\/\d+\/$/);

    const orderId = extractOrderIdFromUrl(page.url());
    const response = await page.request.get(`/api/v1/orders/${orderId}/`);
    expect(response.ok()).toBeTruthy();
    const order = await response.json();
    expect(order.payment_method).toBe('momo');
    expect(order.payment_status).toBe('paid');
    expect(order.transaction_id).toMatch(/^MOCK-MOMO-/);

    diagnostics.assertClean();
  });

  test('dashboard and reader layouts avoid horizontal overflow', async ({ page }) => {
    const diagnostics = attachUiDiagnostics(page);

    await loginAs(page, 'admin', 'admin123');

    await page.goto('/dashboard/');
    await expect(page.locator('body')).toContainText('Dashboard');
    await expectNoHorizontalOverflow(page);

    await page.goto('/ebooks/');
    const firstReadLink = page.locator('a[href*="/read/"]').first();
    await expect(firstReadLink).toBeVisible();
    await firstReadLink.click();
    await expect(page).toHaveURL(/\/books\/\d+\/read\/$/);
    await expectNoHorizontalOverflow(page);

    diagnostics.assertClean();
  });

  test('dashboard RBAC allows staff roles and rejects customers', async ({ page }) => {
    const diagnostics = attachUiDiagnostics(page);

    await loginAsDemo(page);
    await page.goto('/dashboard/');
    await expect(page).toHaveURL(/\/admin\/login\/\?next=\/dashboard\//);

    await page.context().clearCookies();
    await loginAs(page, 'admin', 'admin123');
    await page.goto('/dashboard/');
    await expect(page).toHaveURL(/\/dashboard\/$/);
    await expect(page.locator('body')).toContainText('Dashboard');

    await page.context().clearCookies();
    await loginAs(page, 'support', 'support123');
    await page.goto('/dashboard/orders/');
    await expect(page).toHaveURL(/\/dashboard\/orders\/$/);
    await expect(page.locator('table')).toBeVisible();
    await expectNoHorizontalOverflow(page);

    diagnostics.assertClean();
  });

  test('health probes return expected JSON', async ({ request }) => {
    const live = await request.get('/health/live/');
    expect(live.ok()).toBeTruthy();
    await expect(live).toBeOK();
    expect(await live.json()).toMatchObject({ status: 'healthy', check: 'liveness' });

    const ready = await request.get('/health/ready/');
    expect(ready.ok()).toBeTruthy();
    await expect(ready).toBeOK();
    expect(await ready.json()).toMatchObject({ status: 'ready' });
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
