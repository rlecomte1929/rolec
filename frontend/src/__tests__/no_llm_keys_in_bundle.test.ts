/**
 * Guard: Anthropic key-reading code must never live under src/ (the Vite
 * bundle graph). The policy-builder eval harness lives in frontend/eval/.
 */
import { readFileSync, readdirSync, statSync } from 'fs';
import { join } from 'path';
import { describe, it, expect } from 'vitest';

const SRC = join(__dirname, '..');
const NEEDLES = [
  'VITE_' + 'ANTHROPIC_API_KEY',
  'api.anthropic' + '.com',
];

function walkTsFiles(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) {
      out.push(...walkTsFiles(p));
      continue;
    }
    if (/\.(ts|tsx|js|jsx)$/.test(name)) out.push(p);
  }
  return out;
}

describe('no LLM keys in the Vite src tree', () => {
  it('has zero hits for the Anthropic env var name or API host under src/', () => {
    const hits: string[] = [];
    for (const file of walkTsFiles(SRC)) {
      const text = readFileSync(file, 'utf8');
      for (const needle of NEEDLES) {
        if (text.includes(needle)) {
          hits.push(`${file.slice(SRC.length + 1)}: ${needle}`);
        }
      }
    }
    expect(hits).toEqual([]);
  });
});
