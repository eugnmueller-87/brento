/* How this browser shows that it was let in, without ever saying its word.

   Brento's icon opens the page with a ticket. The page trades it once for a word of its own and keeps that in this
   browser's storage, which no other address can read, not even another port on this computer. After that the word
   never travels again: every request is signed with it, for one address and for one run of Brento, and the answer is
   signed as well. So an open page neither believes a program that takes Brento's place nor tells it anything that is
   good for more. There is no cookie that a browser would send by itself. The limits are in docs/BLUEPRINT.md.

   SHA-256 and HMAC are written out here because a browser only offers its own on addresses it calls secure. */
(function (root) {
  'use strict';

  const KEY = 'brento:word';
  const K = [], H = [];
  const bits = (x) => ((x - Math.floor(x)) * 4294967296) | 0;
  for (let n = 2; K.length < 64; n += 1) {
    let prime = true;
    for (let f = 2; f * f <= n; f += 1) if (n % f === 0) prime = false;
    if (!prime) continue;
    if (H.length < 8) H.push(bits(Math.pow(n, 1 / 2)));
    K.push(bits(Math.pow(n, 1 / 3)));
  }

  const turn = (x, n) => (x >>> n) | (x << (32 - n));
  function sha256(bytes) {
    const words = new Uint32Array((((bytes.length + 8) >> 6) + 1) * 16);
    for (let i = 0; i < bytes.length; i += 1) words[i >> 2] |= bytes[i] << (24 - (i % 4) * 8);
    words[bytes.length >> 2] |= 0x80 << (24 - (bytes.length % 4) * 8);
    words[words.length - 2] = Math.floor(bytes.length / 536870912);
    words[words.length - 1] = bytes.length << 3;
    const h = Int32Array.from(H), w = new Int32Array(64);
    for (let at = 0; at < words.length; at += 16) {
      let a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], x = h[7];
      for (let i = 0; i < 64; i += 1) {
        if (i < 16) w[i] = words[at + i];
        else {
          const p = w[i - 15], q = w[i - 2];
          w[i] = (turn(p, 7) ^ turn(p, 18) ^ (p >>> 3)) + w[i - 7] + (turn(q, 17) ^ turn(q, 19) ^ (q >>> 10)) + w[i - 16];
        }
        const t1 = (x + (turn(e, 6) ^ turn(e, 11) ^ turn(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) | 0;
        const t2 = ((turn(a, 2) ^ turn(a, 13) ^ turn(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) | 0;
        x = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
      }
      h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += x;
    }
    const out = new Uint8Array(32);
    for (let i = 0; i < 32; i += 1) out[i] = h[i >> 2] >>> (24 - (i % 4) * 8);
    return out;
  }

  const utf8 = (text) => new TextEncoder().encode(text);
  const hex = (bytes) => Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  const hash = (text) => hex(sha256(utf8(text)));
  function hmac(key, text) {
    const block = new Uint8Array(64), k = utf8(key);
    block.set(k.length > 64 ? sha256(k) : k);
    const padded = (pad, bytes) => {
      const all = new Uint8Array(64 + bytes.length);
      all.set(block.map((b) => b ^ pad));
      all.set(bytes, 64);
      return all;
    };
    return hex(sha256(padded(0x5c, sha256(padded(0x36, utf8(text))))));
  }

  /* The header for one request: who signs, when, what the body is, for which run, and the signature over all of it and
     the address. */
  function header(word, run, method, path, host, body, now) {
    const sum = body ? hash(body) : '-';
    return [word.id, now, sum, run, hmac(word.word, [method, path, host, now, sum, run].join('\n'))].join('.');
  }
  /* What the answer to such a request is signed with. */
  const answer = (word, head) => hmac(word.word, 'answer\n' + head.split('.')[4]);

  const api = { KEY, hash, hmac, header, answer };
  if (typeof module !== 'undefined') module.exports = api;
  else root.BrentoSign = api;
})(this);
