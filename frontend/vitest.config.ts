import { defineConfig } from 'vitest/config';
import angular from '@analogjs/vite-plugin-angular'; // If using Analog/Vite
import path from 'path';
import { fileURLToPath } from 'url';

// Create __dirname equivalent for ES Modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    // setupFiles: ['./src/test-setup.ts'],
    include: ['src/**/*.spec.ts'],
    // Use an absolute path to ensure Vitest finds the file
    setupFiles: [path.resolve(__dirname, './src/test-setup.ts')],
    // This allows Vitest to find your environment files
    alias: {
      '@env': path.resolve(__dirname, './src/environments'),
    },
  },
  plugins: [
  angular({
    jit: true, // Forces Just-In-Time compilation of templates
    tsconfig: './tsconfig.spec.json'
  })
],
});