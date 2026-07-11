// AIQ-1492 — shared screenshot capture/compression util.
// Same options the tester FeedbackWidget uses (scale 0.4 → ~40% dimensions, JPEG 0.65),
// so an admin-captured screenshot has the same payload size + format as a widget one and
// is served unchanged by GET /api/admin/feedback/{stream}/{id}/screenshot.
export async function captureScreenshotDataUrl(ignoreEl?: HTMLElement | null): Promise<string> {
  const { default: html2canvas } = await import('html2canvas');
  const canvas = await html2canvas(document.body, {
    useCORS: true,
    allowTaint: true,
    logging: false,
    scale: 0.4,
    ignoreElements: (el) => (ignoreEl ? el === ignoreEl : false),
  });
  return canvas.toDataURL('image/jpeg', 0.65);
}
