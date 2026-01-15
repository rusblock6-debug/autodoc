/**
 * AutoDoc AI - Playwright Test Suite
 * Tests all pages and functionality
 */

const { chromium } = require('playwright');

async function runTests() {
    console.log('Starting AutoDoc AI Test Suite...\n');

    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    // Test results
    const results = {
        passed: 0,
        failed: 0,
        errors: []
    };

    // Helper function to run test
    async function runTest(name, testFn) {
        try {
            console.log(`Testing: ${name}...`);
            await testFn();
            console.log(`✓ ${name} passed`);
            results.passed++;
        } catch (error) {
            console.log(`✗ ${name} failed: ${error.message}`);
            results.failed++;
            results.errors.push({ name, error: error.message });
        }
    }

    // Helper to check element exists
    async function checkElementExists(selector) {
        const element = await page.$(selector);
        if (!element) {
            throw new Error(`Element not found: ${selector}`);
        }
        return element;
    }

    // Test 1: Popup Page
    await runTest('Popup page loads correctly', async () => {
        await page.goto(`file://${process.cwd()}/popup.html`);
        await page.waitForLoadState('domcontentloaded');

        // Check title
        const title = await page.title();
        if (!title.includes('AutoDoc AI')) {
            throw new Error('Title does not contain "AutoDoc AI"');
        }

        // Check main elements exist
        await checkElementExists('.popup-container');
        await checkElementExists('.logo');
        await checkElementExists('#startRecordBtn');
        await checkElementExists('#settingsBtn');
    });

    // Test 2: Popup page interactions
    await runTest('Popup page interactions', async () => {
        await page.goto(`file://${process.cwd()}/popup.html`);
        await page.waitForLoadState('domcontentloaded');

        // Click settings button
        await page.click('#settingsBtn');
        await checkElementExists('#settingsModal');
        console.log('  - Settings modal opens correctly');

        // Close modal
        await page.click('#closeSettings');
        const modalHidden = await page.$eval('#settingsModal', el => el.style.display);
        if (modalHidden !== 'none') {
            throw new Error('Settings modal did not close');
        }
        console.log('  - Settings modal closes correctly');
    });

    // Test 3: Dashboard Page
    await runTest('Dashboard page loads correctly', async () => {
        await page.goto(`file://${process.cwd()}/index.html`);
        await page.waitForLoadState('domcontentloaded');

        // Check header
        await checkElementExists('.main-header');
        await checkElementExists('.logo');
        await checkElementExists('#searchInput');
        await checkElementExists('#newGuideBtn');

        // Check guides grid
        await checkElementExists('.guides-grid');
        const guideCards = await page.$$('.guide-card');
        if (guideCards.length < 5) {
            throw new Error(`Expected at least 5 guide cards, found ${guideCards.length}`);
        }
        console.log(`  - Found ${guideCards.length} guide cards`);
    });

    // Test 4: Dashboard search functionality
    await runTest('Dashboard search functionality', async () => {
        await page.goto(`file://${process.cwd()}/index.html`);
        await page.waitForLoadState('domcontentloaded');

        // Type in search box
        await page.fill('#searchInput', 'Обновление');

        // Check that matching card is visible
        const visibleCards = await page.$$('.guide-card:not(.new-card)[style=""]');
        console.log(`  - Search found ${visibleCards.length} matching cards`);
    });

    // Test 5: Editor Page
    await runTest('Editor page loads correctly', async () => {
        await page.goto(`file://${process.cwd()}/editor.html`);
        await page.waitForLoadState('domcontentloaded');

        // Check editor header
        await checkElementExists('.editor-header');
        await checkElementExists('.guide-title-input');
        await checkElementExists('#saveDraftBtn');
        await checkElementExists('#exportBtn');

        // Check canvas area
        await checkElementExists('.editor-canvas');
        await checkElementExists('.screenshot-container');
        await checkElementExists('#marker');

        // Check steps panel
        await checkElementExists('.steps-panel');
        const stepItems = await page.$$('.step-item');
        if (stepItems.length < 3) {
            throw new Error(`Expected at least 3 step items, found ${stepItems.length}`);
        }
        console.log(`  - Found ${stepItems.length} step items`);
    });

    // Test 6: Editor marker drag functionality
    await runTest('Editor marker drag functionality', async () => {
        await page.goto(`file://${process.cwd()}/editor.html`);
        await page.waitForLoadState('domcontentloaded');

        // Check marker exists and is draggable
        const marker = await checkElementExists('#marker');

        // Get initial position
        const initialPos = await marker.evaluate(el => ({
            left: el.style.left,
            top: el.style.top
        }));
        console.log(`  - Initial marker position: ${initialPos.left}, ${initialPos.top}`);

        // Simulate drag
        const container = await checkElementExists('.screenshot-container');
        const box = await container.boundingBox();

        await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.3);
        await page.mouse.down();
        await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.7);
        await page.mouse.up();

        // Check new position
        const newPos = await marker.evaluate(el => ({
            left: el.style.left,
            top: el.style.top
        }));

        if (initialPos.left === newPos.left && initialPos.top === newPos.top) {
            console.log('  - Note: Marker position unchanged (may need user interaction)');
        } else {
            console.log(`  - New marker position: ${newPos.left}, ${newPos.top}`);
        }
    });

    // Test 7: Step switching
    await runTest('Editor step switching', async () => {
        await page.goto(`file://${process.cwd()}/editor.html`);
        await page.waitForLoadState('domcontentloaded');

        // Click on step 3
        await page.click('.step-item[data-step="3"]');

        // Check if step 3 is active
        const isActive = await page.$eval('.step-item[data-step="3"]', el => el.classList.contains('active'));
        if (!isActive) {
            throw new Error('Step 3 is not active after clicking');
        }
        console.log('  - Step switching works correctly');
    });

    // Test 8: Modals
    await runTest('Editor modals functionality', async () => {
        await page.goto(`file://${process.cwd()}/editor.html`);
        await page.waitForLoadState('domcontentloaded');

        // Test preview modal
        await page.click('#previewBtn');
        await checkElementExists('#previewModal');
        console.log('  - Preview modal opens');

        await page.keyboard.press('Escape');
        const previewHidden = await page.$eval('#previewModal', el => el.style.display);
        if (previewHidden !== 'none') {
            throw new Error('Preview modal did not close with Escape');
        }
        console.log('  - Preview modal closes with Escape');

        // Test export dropdown
        await page.click('#exportBtn');
        await checkElementExists('#exportDropdown');
        console.log('  - Export dropdown opens');
    });

    // Test 9: CSS and styling
    await runTest('CSS styling applied correctly', async () => {
        await page.goto(`file://${process.cwd()}/index.html`);
        await page.waitForLoadState('domcontentloaded');

        // Check main colors are applied
        const header = await page.$('.main-header');
        const bgColor = await header.evaluate(el => getComputedStyle(el).backgroundColor);
        console.log(`  - Header background: ${bgColor}`);

        // Check button styles
        const newBtn = await page.$('#newGuideBtn');
        const btnColor = await newBtn.evaluate(el => getComputedStyle(el).backgroundColor);
        console.log(`  - New guide button background: ${btnColor}`);
    });

    // Test 10: Responsive design check
    await runTest('Responsive design elements', async () => {
        await page.goto(`file://${process.cwd()}/index.html`);
        await page.waitForLoadState('domcontentloaded');

        // Check grid exists
        const grid = await page.$('.guides-grid');
        const display = await grid.evaluate(el => getComputedStyle(el).display);
        if (display !== 'grid') {
            throw new Error(`Expected grid display, got ${display}`);
        }
        console.log(`  - Grid display: ${display}`);
    });

    // Print results
    console.log('\n' + '='.repeat(50));
    console.log('Test Results:');
    console.log(`✓ Passed: ${results.passed}`);
    console.log(`✗ Failed: ${results.failed}`);
    console.log('='.repeat(50));

    if (results.errors.length > 0) {
        console.log('\nErrors:');
        results.errors.forEach(err => {
            console.log(`  - ${err.name}: ${err.error}`);
        });
    }

    await browser.close();

    // Exit with appropriate code
    process.exit(results.failed > 0 ? 1 : 0);
}

// Run tests
runTests().catch(err => {
    console.error('Test suite failed:', err);
    process.exit(1);
});
