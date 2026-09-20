#!/usr/bin/env node
const https = require('https');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// Config
const M3U8_PATH = process.argv[2];
const OUT_TS = process.argv[3];
const SEG_DIR = process.argv[4];
const KEY_ASCII = process.argv[5];  // first 16 bytes as ASCII string
const IV_HEX = process.argv[6];
const CONCURRENCY = parseInt(process.argv[7] || "64");

const key = Buffer.from(KEY_ASCII, 'ascii');
const iv = Buffer.from(IV_HEX, 'hex');

// Parse m3u8 to get segment URLs
const m3u8 = fs.readFileSync(M3U8_PATH, 'utf-8');
const segmentUrls = m3u8.split('\n').filter(l => l.startsWith('http')).map(l => l.trim());
console.log(`Found ${segmentUrls.length} segments`);
console.log(`Key: ${KEY_ASCII} (${key.length} bytes)`);
console.log(`IV: ${IV_HEX}`);
console.log(`Concurrency: ${CONCURRENCY}`);

// Download a single URL with redirect support
function download(url, redirects = 0) {
  return new Promise((resolve, reject) => {
    if (redirects > 5) return reject(new Error('Too many redirects'));
    const mod = url.startsWith('https') ? https : require('http');
    mod.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36',
        'Referer': 'https://v-glive.gaodun.com/'
      }
    }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return resolve(download(new URL(res.headers.location, url).href, redirects + 1));
      }
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`HTTP ${res.statusCode} for ${url.substring(0, 100)}`));
      }
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve(Buffer.concat(chunks)));
      res.on('error', reject);
    }).on('error', reject);
  });
}

// Decrypt a segment (AES-128-CBC, same IV per HLS spec)
function decrypt(encData) {
  const decipher = crypto.createDecipheriv('aes-128-cbc', key, iv);
  decipher.setAutoPadding(false);
  return Buffer.concat([decipher.update(encData), decipher.final()]);
}

// Main: download with concurrency, decrypt, write to output
async function main() {
  // Ensure segment dir exists
  fs.mkdirSync(SEG_DIR, { recursive: true });

  let completed = 0;
  let failed = [];
  const total = segmentUrls.length;
  const startTime = Date.now();

  // Create write stream for merged output
  const outStream = fs.createWriteStream(OUT_TS);

  // We need to write segments in order, so download in parallel but write sequentially
  // Use a promise pool with ordered results
  const results = new Array(total);
  let nextWrite = 0;

  async function worker(idx) {
    const url = segmentUrls[idx];
    const segFile = path.join(SEG_DIR, `${idx}.ts`);

    // Check if already downloaded and decrypted
    try {
      const decFile = path.join(SEG_DIR, `${idx}.dec.ts`);
      if (fs.existsSync(decFile)) {
        results[idx] = fs.readFileSync(decFile);
      } else {
        const enc = await download(url);
        const dec = decrypt(enc);
        fs.writeFileSync(decFile, dec);
        results[idx] = dec;
      }
    } catch (e) {
      failed.push({ idx, error: e.message });
      results[idx] = null;
    }

    completed++;
    if (completed % 25 === 0 || completed === total) {
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      const pct = ((completed / total) * 100).toFixed(1);
      process.stdout.write(`\rProgress: ${completed}/${total} (${pct}%) - ${elapsed}s - failed: ${failed.length}`);
    }

    // Try to write sequential results
    while (nextWrite < total && results[nextWrite] !== undefined) {
      if (results[nextWrite]) {
        outStream.write(results[nextWrite]);
      }
      nextWrite++;
    }
  }

  // Launch workers with concurrency limit
  let nextIdx = 0;
  async function pool() {
    const workers = [];
    for (let i = 0; i < CONCURRENCY; i++) {
      workers.push((async () => {
        while (nextIdx < total) {
          const idx = nextIdx++;
          await worker(idx);
        }
      })());
    }
    await Promise.all(workers);
  }

  await pool();

  await new Promise((resolve, reject) => {
    outStream.end(() => resolve());
    outStream.on('error', reject);
  });

  console.log(`\n\nDone! Output: ${OUT_TS}`);
  const stats = fs.statSync(OUT_TS);
  console.log(`Size: ${(stats.size / 1024 / 1024).toFixed(1)} MB`);
  if (failed.length > 0) {
    console.log(`\nFailed segments (${failed.length}):`);
    failed.forEach(f => console.log(`  segment ${f.idx}: ${f.error}`));
  }
}

main().catch(e => { console.error(e); process.exit(1); });
