// Adds the jest-dom matchers (toBeInTheDocument, toHaveAttribute, ...) and
// auto-cleans the rendered DOM between tests.
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => cleanup());
