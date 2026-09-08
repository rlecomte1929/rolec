#!/usr/bin/env tsx
import sharp from 'sharp';
import { randomUUID } from 'crypto';

const ORIGINAL = 'https://storage.googleapis.com/audos-images/brand-icons/52ac3854-f26a-46f5-9259-0565c30ac6b8.png';

async function main() {
  console.log('[resize-logo] Bucket env:', process.env.GCS_BUCKET_NAME);
  const gcsServiceModule = await import('/home/runner/workspace/server/services/gcs-service.ts');
  const gcsService = gcsServiceModule.gcsService;
  if (!gcsService.isAvailable()) {
    console.error('[resize-logo] GCS not available');
    process.exit(1);
  }

  console.log('[resize-logo] Downloading original PNG...');
  const res = await fetch(ORIGINAL);
  if (!res.ok) {
    console.error('[resize-logo] Failed to download original:', res.status);
    process.exit(1);
  }
  const original = Buffer.from(await res.arrayBuffer());
  const meta = await sharp(original).metadata();
  console.log(`[resize-logo] Original: ${meta.width}x${meta.height}, ${(original.length / 1024).toFixed(1)}KB, format=${meta.format}`);

  // Render box is 28x28 CSS px; 84 = 3x for crisp retina. Keep exact same mark.
  const SIZE = 84;

  const webp = await sharp(original)
    .resize(SIZE, SIZE, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .webp({ quality: 90 })
    .toBuffer();
  console.log(`[resize-logo] WebP ${SIZE}x${SIZE}: ${(webp.length / 1024).toFixed(2)}KB`);

  const png = await sharp(original)
    .resize(SIZE, SIZE, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .png({ compressionLevel: 9, palette: true })
    .toBuffer();
  console.log(`[resize-logo] PNG  ${SIZE}x${SIZE}: ${(png.length / 1024).toFixed(2)}KB`);

  // Prefer WebP (modern, smaller). Fall back to PNG only if WebP somehow larger.
  const useWebp = webp.length <= png.length;
  const buffer = useWebp ? webp : png;
  const ext = useWebp ? 'webp' : 'png';
  const contentType = useWebp ? 'image/webp' : 'image/png';
  const filename = `brand-icons/drm-logo-${SIZE}-${randomUUID()}.${ext}`;

  console.log(`[resize-logo] Uploading ${ext} (${(buffer.length / 1024).toFixed(2)}KB) as ${filename}...`);
  const url = await gcsService.uploadBuffer(buffer, filename, contentType, {
    cacheControl: 'public, max-age=31536000, immutable',
  });

  console.log('');
  console.log('SUCCESS');
  console.log('SMALL_LOGO_URL=' + url);
}

main().catch((e) => {
  console.error('[resize-logo] Error:', e);
  process.exit(1);
});
