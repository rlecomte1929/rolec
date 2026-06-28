/**
 * AIQ-174 — PdfCoordinateMapper coord-math tests.
 *
 * Locks down the screen↔PDF-point conversion that drives the entire mapper.
 * The component itself depends on react-pdf which doesn't mount cleanly in
 * jsdom, so we test the pure helpers directly. The math is the highest-bug
 * surface area of the component; everything else is React state plumbing.
 */
import { describe, expect, it, vi } from 'vitest';
import {
  pdfPointToScreen,
  screenToPdfPoint,
  type PageScale,
} from '../PdfCoordinateMapper';

// react-pdf transitively loads pdfjs-dist@4.8.69, whose node_utils.js calls
// Promise.withResolvers() (Node 22+) at import time — which crashes under the
// jsdom/vitest runtime. The component imports react-pdf only for <Document>/<Page>
// rendering; these tests exercise the pure coord-math helpers and never render it.
// Mocking at the react-pdf boundary keeps the real module (and pdfjs-dist) out of
// the test entirely. (vi.mock is hoisted above the imports below by vitest.)
vi.mock('react-pdf', () => ({
  Document: () => null,
  Page: () => null,
  pdfjs: { GlobalWorkerOptions: { workerSrc: '' }, version: '4.8.69' },
}));

// A4 in PDF points (595 × 842), rendered at the default 700px width.
const A4_SCALE: PageScale = {
  renderedWidth: 700,
  pdfWidth: 595,
  pdfHeight: 842,
};

// US Letter (612 × 792) at a zoomed-out 350px width — exercises the px-per-pt
// scale at a different magnification.
const LETTER_AT_350: PageScale = {
  renderedWidth: 350,
  pdfWidth: 612,
  pdfHeight: 792,
};

describe('screenToPdfPoint', () => {
  it('returns origin (0, page_height) for a click at the top-left corner', () => {
    const { pdf_x, pdf_y } = screenToPdfPoint(0, 0, A4_SCALE);
    expect(pdf_x).toBe(0);
    // Y is flipped — top of screen is top of page, top of page is pdfHeight.
    expect(pdf_y).toBe(A4_SCALE.pdfHeight);
  });

  it('returns (page_width, 0) at the bottom-right corner of the rendered canvas', () => {
    const { pdf_x, pdf_y } = screenToPdfPoint(
      A4_SCALE.renderedWidth,
      (A4_SCALE.renderedWidth * A4_SCALE.pdfHeight) / A4_SCALE.pdfWidth,
      A4_SCALE,
    );
    expect(pdf_x).toBe(A4_SCALE.pdfWidth);
    expect(pdf_y).toBe(0);
  });

  it('maps the canvas center to the PDF page center', () => {
    const cssHeight =
      (A4_SCALE.renderedWidth * A4_SCALE.pdfHeight) / A4_SCALE.pdfWidth;
    const { pdf_x, pdf_y } = screenToPdfPoint(
      A4_SCALE.renderedWidth / 2,
      cssHeight / 2,
      A4_SCALE,
    );
    // Allow ±0.5 pt due to rounding to 2 decimals.
    expect(pdf_x).toBeCloseTo(A4_SCALE.pdfWidth / 2, 0);
    expect(pdf_y).toBeCloseTo(A4_SCALE.pdfHeight / 2, 0);
  });

  it('clamps negative offsets to the page boundary', () => {
    const { pdf_x, pdf_y } = screenToPdfPoint(-50, -50, A4_SCALE);
    expect(pdf_x).toBe(0);
    expect(pdf_y).toBe(A4_SCALE.pdfHeight);
  });

  it('clamps offsets beyond the canvas to the page boundary', () => {
    const cssHeight =
      (A4_SCALE.renderedWidth * A4_SCALE.pdfHeight) / A4_SCALE.pdfWidth;
    const { pdf_x, pdf_y } = screenToPdfPoint(
      A4_SCALE.renderedWidth + 100,
      cssHeight + 100,
      A4_SCALE,
    );
    expect(pdf_x).toBe(A4_SCALE.pdfWidth);
    expect(pdf_y).toBe(0);
  });

  it('handles zoomed-out rendering (smaller renderedWidth)', () => {
    // Click at 175px on a 350px-wide rendering of US Letter (612pt wide).
    // 175/350 = 0.5 → pdf_x should be 306pt (half of 612).
    const { pdf_x } = screenToPdfPoint(175, 0, LETTER_AT_350);
    expect(pdf_x).toBe(306);
  });

  it('rounds to 2 decimal places to keep payloads compact', () => {
    // Pick an offset that would yield many decimals without rounding.
    const { pdf_x } = screenToPdfPoint(123, 0, A4_SCALE);
    // pdf_x = 123 * (595/700) ≈ 104.5499... → 104.55
    expect(pdf_x).toBe(104.55);
  });
});

describe('pdfPointToScreen', () => {
  it('round-trips with screenToPdfPoint to within 1px', () => {
    const samples: Array<[number, number]> = [
      [0, 0],
      [350, 200],
      [700, 850],
      [50, 50],
      [350, 421],
    ];
    for (const [sx, sy] of samples) {
      const { pdf_x, pdf_y } = screenToPdfPoint(sx, sy, A4_SCALE);
      const { left, top } = pdfPointToScreen(pdf_x, pdf_y, A4_SCALE);
      expect(Math.abs(left - Math.max(0, Math.min(A4_SCALE.renderedWidth, sx)))).toBeLessThan(1);
      const cssHeight = (A4_SCALE.renderedWidth * A4_SCALE.pdfHeight) / A4_SCALE.pdfWidth;
      expect(
        Math.abs(top - Math.max(0, Math.min(cssHeight, sy))),
      ).toBeLessThan(1);
    }
  });

  it('places the page origin (0, 0) at the bottom-left of the canvas', () => {
    const { left, top } = pdfPointToScreen(0, 0, A4_SCALE);
    expect(left).toBe(0);
    const cssHeight =
      (A4_SCALE.renderedWidth * A4_SCALE.pdfHeight) / A4_SCALE.pdfWidth;
    expect(top).toBeCloseTo(cssHeight, 5);
  });

  it('places (page_width, page_height) at the top-right of the canvas', () => {
    const { left, top } = pdfPointToScreen(
      A4_SCALE.pdfWidth,
      A4_SCALE.pdfHeight,
      A4_SCALE,
    );
    expect(left).toBe(A4_SCALE.renderedWidth);
    expect(top).toBe(0);
  });
});
