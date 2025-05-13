/*
  Almost all of this was created as boiler plate code via 'npx init playwright'
 */

import { defineConfig, devices } from '@playwright/test';
// @ts-ignore
import path from 'path';

// Read environment variables from file.
// https://github.com/motdotla/dotenv
// require('dotenv').config(); // Uncomment if you use process.env in your config, though usually not needed directly here

const FRONTEND_PORT = 5173;
const BACKEND_PORT = 8000;
const FRONTEND_URL = `http://localhost:${FRONTEND_PORT}`;
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({

  testDir: './e2e', // Directory containing the test files

  fullyParallel: true, // Run tests in files in parallel

  forbidOnly: !!process.env.CI, // Fail the build on CI if you accidentally left test.only in the source code.

  retries: process.env.CI ? 2 : 0, // Retry on CI only


  workers: process.env.CI ? 1 : undefined, // Opt out of parallel tests on CI. Adjust workers based on your CI resources

  reporter: 'html', // Generates a nice HTML report

  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    // Base URL to use in actions like `await page.goto('/')`
    baseURL: FRONTEND_URL,

    // Collect trace when retrying the failed test.
    trace: 'on-first-retry', // or 'retain-on-failure' or 'on'
  },

  /* major browsers */
  projects: [
    {
      name: 'chromium',
      use: {...devices['Desktop Chrome']},
    },

    {
      name: 'firefox',
      use: {...devices['Desktop Firefox']},
    },

    {
      name: 'webkit',
      use: {...devices['Desktop Safari']},
    },

    /* mobile viewports. */
    {
      name: 'Mobile Chrome',
      use: {...devices['Pixel 5']},
    },
    {
      name: 'Mobile Safari',
      use: {...devices['iPhone 12']},
    },

    /* branded browsers. */
    {
      name: 'Microsoft Edge',
      use: {...devices['Desktop Edge'], channel: 'msedge'},
    },
    {
      name: 'Google Chrome',
      use: {...devices['Desktop Chrome'], channel: 'chrome'},
    },
  ],
  // run dev servers for testing
  webServer: [{
      command: 'npm run dev',
      cwd: path.join(__dirname, 'frontend'),
      url: FRONTEND_URL,
      reuseExistingServer: !process.env.CI, // Reuse server if already running locally
      timeout: 120 * 1000,
      stdout: 'pipe', // Pipe stdout for debugging
      stderr: 'pipe', // Pipe stderr for debugging
  },
    {
      command: 'python app.py',
      cwd: path.join(__dirname, 'backend'),
      url: BACKEND_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000, // 2 mins
      stdout: 'pipe',
      stderr: 'pipe',
  }
],});