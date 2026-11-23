/* Scenery drawn by code, seeded by the card, so there are no image files and no image API.
   The picture carries state: a near deadline burns the horizon, an old source fogs the valley. */
(function () {
  'use strict';

  const PALETTES = {
    deadline: { sky: ['#07030b', '#2a0a1e', '#7d1f2d', '#ee6a3e'], accent: '#ff8a5c', aurora: ['#ff4f70', '#ffb35c'], ridge: ['#4a1626', '#080308'], line: '#ffc2a6' },
    pipeline: { sky: ['#020a12', '#052230', '#0a4a4c', '#22a083'], accent: '#6cf5bf', aurora: ['#3df0a8', '#37c4ff'], ridge: ['#0e3a3f', '#01080c'], line: '#a8ffe4' },
    board: { sky: ['#03051a', '#0b1152', '#1d2ba6', '#6677ff'], accent: '#98a5ff', aurora: ['#6f7dff', '#c98bff'], ridge: ['#182068', '#020316'], line: '#c6ceff' },
    brain: { sky: ['#07031a', '#1d0a48', '#4f1b8c', '#c064ea'], accent: '#d09dff', aurora: ['#b47bff', '#ff7ad9'], ridge: ['#311566', '#050216'], line: '#e8d2ff' },
    goals: { sky: ['#0a0703', '#2c1d06', '#74500c', '#e3ad28'], accent: '#ffd166', aurora: ['#ffd166', '#ff9a56'], ridge: ['#3b290b', '#060401'], line: '#ffe8ad' },
    brief: { sky: ['#020a18', '#082342', '#104f84', '#45abe6'], accent: '#86d7ff', aurora: ['#68d0ff', '#7df5e5'], ridge: ['#0d3158', '#010710'], line: '#c6ecff' },
    ask: { sky: ['#040611', '#0f1433', '#1e3a66', '#3c8f9e'], accent: '#7ee8e0', aurora: ['#5be6d8', '#8e9bff'], ridge: ['#16294e', '#02040c'], line: '#c5f4ef' }
  };
  /* Home cards by urgency, from "everything is on fire" down to "all good": red, orange, yellow, blue, green.
     The level sets the colours and the weather; sharp is how jagged the peaks are, 0 is rolling hills. */
  const LEVELS = {
    critical: { pal: { sky: ['#040001', '#260205', '#6e070c', '#ff2a14'], accent: '#ff3b30', aurora: ['#ff1a1a', '#ff6a00'], ridge: ['#3a0507', '#040000'], line: '#ff8f7a' },
      heat: 1, sharp: 2.8, amp: 1.3, freq: 1.5, stars: 0.12 },
    high: { pal: { sky: ['#060201', '#2a0d03', '#8a330a', '#ff8a1e'], accent: '#ff8c2e', aurora: ['#ff6a1a', '#ffb347'], ridge: ['#4a1a07', '#060200'], line: '#ffc999' },
      heat: 0.75, sharp: 2.1, amp: 1.12, freq: 1.2, stars: 0.4 },
    medium: { pal: { sky: ['#090701', '#2c2205', '#8a660e', '#ffd23a'], accent: '#ffd23a', aurora: ['#ffe066', '#ffb347'], ridge: ['#3d2f0a', '#060401'], line: '#fff0b3' },
      heat: 0.45, sharp: 1.7, amp: 1, freq: 1, stars: 0.6 },
    low: { pal: { sky: ['#01030b', '#061838', '#0f3c78', '#4aa3e8'], accent: '#a9d8ff', aurora: ['#5ab8ff', '#7df5e5'], ridge: ['#0b284c', '#01050d'], line: '#c6e6ff' },
      heat: 0.1, sharp: 1.25, amp: 0.78, freq: 0.85, stars: 1 },
    calm: { pal: { sky: ['#0b281b', '#226345', '#62b884', '#e2f7cf'], accent: '#5ee6a8', aurora: ['#b8ffc9', '#f2ffb0'], ridge: ['#2e7448', '#0b2a16'], line: '#e0ffe8' },
      heat: 0, sharp: 0, amp: 0.55, freq: 0.7, stars: 0.2 }
  };
  const PLAIN = { sharp: 1.7, amp: 1, freq: 1, stars: 1 };

  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function hash(text) {
    let h = 2166136261;
    for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }

  function noiseFn(r) {
    const table = new Float32Array(512);
    for (let i = 0; i < 512; i++) table[i] = r();
    function base(x) {
      const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f);
      return table[i & 511] * (1 - u) + table[(i + 1) & 511] * u;
    }
    return function (x, octaves) {
      let sum = 0, amp = 0.5, total = 0, fr = 1;
      for (let o = 0; o < octaves; o++) { sum += base(x * fr + o * 37.1) * amp; total += amp; amp *= 0.5; fr *= 2.03; }
      return sum / total;
    };
  }

  function rgb(hex) { const n = parseInt(hex.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
  function mix(a, b, t) {
    const x = rgb(a), y = rgb(b);
    return 'rgb(' + x.map(function (v, i) { return Math.round(v + (y[i] - v) * t); }).join(',') + ')';
  }
  function alpha(hex, a) { const c = rgb(hex); return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + a + ')'; }

  function paint(cv, o) {
    const w = cv.width, h = cv.height, ctx = cv.getContext('2d');
    const r = rng(hash(o.seed || 'x')), n = noiseFn(r);
    const L = LEVELS[o.level], shape = L || PLAIN;
    const p = L ? L.pal : (PALETTES[o.kind] || PALETTES.brain), heat = L ? L.heat : (o.heat || 0), fog = o.fog || 0;

    const sky = ctx.createLinearGradient(0, 0, 0, h * 0.82);
    sky.addColorStop(0, p.sky[0]);
    sky.addColorStop(0.42, p.sky[1]);
    sky.addColorStop(0.72, p.sky[2]);
    sky.addColorStop(1, p.sky[3]);
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, w, h);

    for (let i = 0, count = 420 * (1 - fog * 0.8) * shape.stars; i < count; i++) {
      const size = r() < 0.06 ? 1.7 : 0.9;
      ctx.fillStyle = 'rgba(255,255,255,' + (0.14 + r() * 0.62) + ')';
      ctx.fillRect(r() * w, r() * r() * h * 0.62, size, size);
    }

    // Drawn small and scaled up: the upscale is the blur, which also works where canvas filters do not.
    const low = document.createElement('canvas');
    low.width = Math.ceil(w / 4); low.height = Math.ceil(h / 4);
    const lx = low.getContext('2d');
    lx.globalCompositeOperation = 'lighter';
    for (let k = 0; k < 4; k++) {
      const base = low.height * (0.1 + r() * 0.28), ph = r() * 40, col = p.aurora[k % 2];
      for (let x = 0; x < low.width; x++) {
        const t = x / low.width;
        const y = base + (n(t * 2.6 + ph, 3) - 0.5) * low.height * 0.5;
        const len = low.height * (0.1 + n(t * 7 + ph, 2) * 0.42);
        const strength = Math.pow(n(t * 3.2 + ph * 2, 2), 2) * 0.95;
        const g = lx.createLinearGradient(0, y - len * 0.8, 0, y + len * 0.3);
        g.addColorStop(0, alpha(col, 0));
        g.addColorStop(0.75, alpha(col, strength * 0.62));
        g.addColorStop(1, alpha(col, 0));
        lx.fillStyle = g;
        lx.fillRect(x, y - len * 0.8, 1, len * 1.1);
      }
    }
    ctx.save();
    ctx.globalCompositeOperation = 'screen';
    ctx.globalAlpha = 0.85 * (1 - fog * 0.55);
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(low, 0, 0, w, h);
    ctx.restore();

    if (o.level === 'critical') storm(ctx, w, h, r);
    if (o.level === 'low') shootingStar(ctx, w, h, r);
    if (o.level === 'medium') birds(ctx, w, h, r);

    const ox = w * (0.66 + r() * 0.2), oy = h * (0.2 + r() * 0.2), radius = h * (0.05 + heat * 0.07 + r() * 0.015);
    const halo = ctx.createRadialGradient(ox, oy, radius * 0.4, ox, oy, radius * (6 + heat * 5));
    halo.addColorStop(0, alpha(p.accent, 0.55 + heat * 0.3));
    halo.addColorStop(0.3, alpha(p.accent, 0.13 + heat * 0.12));
    halo.addColorStop(1, alpha(p.accent, 0));
    ctx.fillStyle = halo;
    ctx.fillRect(0, 0, w, h);
    const disc = ctx.createRadialGradient(ox - radius * 0.3, oy - radius * 0.3, radius * 0.1, ox, oy, radius);
    disc.addColorStop(0, '#ffffff');
    disc.addColorStop(0.55, mix(p.accent, '#ffffff', 0.45));
    disc.addColorStop(1, p.accent);
    ctx.fillStyle = disc;
    ctx.beginPath();
    ctx.arc(ox, oy, radius, 0, Math.PI * 2);
    ctx.fill();

    const glow = ctx.createRadialGradient(ox, h * 0.72, 0, ox, h * 0.72, w * (0.45 + heat * 0.35));
    glow.addColorStop(0, alpha(p.sky[3], 0.3 + heat * 0.55));
    glow.addColorStop(1, alpha(p.sky[3], 0));
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, w, h);

    const layers = 7, step = Math.max(2, Math.round(w / 480));
    for (let i = 0; i < layers; i++) {
      const t = i / (layers - 1);
      const baseY = h * (0.52 + 0.4 * t * t);
      const amp = h * (0.2 - 0.09 * t) * shape.amp;
      const freq = (3.4 - 2 * t) / w * 2 * shape.freq;
      const off = r() * 300;
      const ys = [];
      for (let x = 0; x <= w + step; x += step) {
        // Ridged noise makes peaks; plain noise makes hills.
        const top = shape.sharp ? Math.pow(1 - Math.abs(2 * n(x * freq + off, 4) - 1), shape.sharp) : Math.pow(n(x * freq + off, 3), 1.4);
        ys.push(baseY - top * amp + (n(x * freq * 6 + off, 2) - 0.5) * amp * (shape.sharp ? 0.16 : 0.04));
      }
      const trace = function (shift) {
        ctx.beginPath();
        ys.forEach(function (y, j) { const px = j * step, py = y + shift; if (j) ctx.lineTo(px, py); else ctx.moveTo(px, py); });
      };

      const fill = ctx.createLinearGradient(0, baseY - amp, 0, h);
      const near = mix(p.ridge[0], p.ridge[1], t);
      fill.addColorStop(0, mix(near, p.sky[2], (1 - t) * 0.55));
      fill.addColorStop(0.6, near);
      fill.addColorStop(1, p.ridge[1]);
      trace(0);
      ctx.lineTo(w + step, h); ctx.lineTo(0, h); ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();

      // Contour lines follow the ridge downward, like an engraved map.
      ctx.save();
      ctx.clip();
      const lines = 20;
      for (let c = 1; c <= lines; c++) {
        const d = c * c * 0.62 + c * 3.2;
        trace(d);
        ctx.strokeStyle = alpha(p.line, (0.15 + 0.12 * (1 - t)) * (1 - c / (lines + 2)));
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      ctx.restore();

      trace(0);
      ctx.strokeStyle = alpha(p.line, 0.26 * (1 - t) + 0.08);
      ctx.lineWidth = 1.2;
      ctx.stroke();

      if (i < layers - 1) {
        const mist = ctx.createLinearGradient(0, baseY - amp * 0.2, 0, baseY + h * 0.14);
        mist.addColorStop(0, alpha(p.sky[2], 0));
        mist.addColorStop(0.55, alpha(p.sky[3], 0.08 + (1 - t) * 0.1 + fog * 0.2));
        mist.addColorStop(1, alpha(p.sky[2], 0));
        ctx.fillStyle = mist;
        ctx.fillRect(0, baseY - amp * 0.2, w, h * 0.34);
      }
    }

    if (fog > 0.2) {
      for (let k = 0; k < 7; k++) {
        const y = h * (0.42 + r() * 0.5), band = h * (0.1 + r() * 0.16);
        const g = ctx.createLinearGradient(0, y - band, 0, y + band);
        g.addColorStop(0, 'rgba(190,200,215,0)');
        g.addColorStop(0.5, 'rgba(190,200,215,' + 0.17 * fog + ')');
        g.addColorStop(1, 'rgba(190,200,215,0)');
        ctx.fillStyle = g;
        ctx.fillRect(0, y - band, w, band * 2);
      }
    }

    if (o.level === 'critical') embers(ctx, w, h, r, 190, 0.5);
    if (o.level === 'high') embers(ctx, w, h, r, 60, 0.22);
    if (o.level === 'calm') bloom(ctx, w, h, r);
    grain(ctx, w, h, r);
  }

  // Film grain over everything, so flat fills read as a picture and not as a chart.
  function grain(ctx, w, h, r) {
    const tile = document.createElement('canvas');
    tile.width = tile.height = 128;
    const tx = tile.getContext('2d'), img = tx.createImageData(128, 128);
    for (let i = 0; i < img.data.length; i += 4) {
      const v = r() * 255;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
      img.data[i + 3] = 26;
    }
    tx.putImageData(img, 0, 0);
    ctx.save();
    ctx.globalCompositeOperation = 'overlay';
    ctx.fillStyle = ctx.createPattern(tile, 'repeat');
    ctx.fillRect(0, 0, w, h);
    ctx.restore();
  }

  /* Weather for the levels. Each draws on top of the scene and takes the same seeded random, so a card keeps its picture. */

  // Smoke rolling over a red sky, then forks of lightning down to the peaks.
  function storm(ctx, w, h, r) {
    for (let k = 0; k < 9; k++) {
      const cx = r() * w, cy = h * (0.05 + r() * 0.3), rad = h * (0.18 + r() * 0.25);
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rad);
      g.addColorStop(0, 'rgba(12,0,0,' + (0.35 + r() * 0.3) + ')');
      g.addColorStop(1, 'rgba(12,0,0,0)');
      ctx.fillStyle = g;
      ctx.fillRect(cx - rad, cy - rad, rad * 2, rad * 2);
    }
    const bolt = function (x, y, len, width, depth) {
      const pts = [[x, y]];
      for (let s = 0; s < 14; s++) { x += (r() - 0.5) * w * 0.035; y += len / 14; pts.push([x, y]); }
      [[26, 'rgba(255,120,90,0.14)'], [10, 'rgba(255,200,190,0.35)'], [width, 'rgba(255,255,255,1)']].forEach(function (pass) {
        ctx.beginPath();
        pts.forEach(function (pt, j) { if (j) ctx.lineTo(pt[0], pt[1]); else ctx.moveTo(pt[0], pt[1]); });
        ctx.lineWidth = pass[0];
        ctx.strokeStyle = pass[1];
        ctx.lineJoin = 'round';
        ctx.stroke();
      });
      if (depth < 2) for (let b = 0; b < 2; b++) { const at = pts[3 + Math.floor(r() * 8)]; bolt(at[0], at[1], len * 0.45, width * 0.6, depth + 1); }
    };
    const count = 2 + Math.floor(r() * 2);
    for (let b = 0; b < count; b++) bolt(w * (0.12 + r() * 0.76), 0, h * (0.42 + r() * 0.18), 3.6, 0);
    const flash = ctx.createRadialGradient(w * 0.5, 0, 0, w * 0.5, 0, w * 0.7);
    flash.addColorStop(0, 'rgba(255,80,60,0.18)');
    flash.addColorStop(1, 'rgba(255,80,60,0)');
    ctx.fillStyle = flash;
    ctx.fillRect(0, 0, w, h);
  }

  // Sparks rising from below, and a glow at the bottom like the ground is burning.
  function embers(ctx, w, h, r, count, glow) {
    const fire = ctx.createLinearGradient(0, h, 0, h * 0.7);
    fire.addColorStop(0, 'rgba(255,70,10,' + glow + ')');
    fire.addColorStop(1, 'rgba(255,70,10,0)');
    ctx.fillStyle = fire;
    ctx.fillRect(0, h * 0.7, w, h * 0.3);
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < count; i++) {
      const x = r() * w, y = h * (1 - Math.pow(r(), 0.7) * 0.85), s = 0.8 + r() * 2.2;
      const g = ctx.createRadialGradient(x, y, 0, x, y, s * 4);
      g.addColorStop(0, 'rgba(255,' + Math.round(150 + r() * 90) + ',60,0.9)');
      g.addColorStop(1, 'rgba(255,90,20,0)');
      ctx.fillStyle = g;
      ctx.fillRect(x - s * 4, y - s * 4, s * 8, s * 8);
    }
    ctx.restore();
  }

  // A few birds high up on a warm afternoon.
  function birds(ctx, w, h, r) {
    ctx.strokeStyle = 'rgba(40,24,6,0.7)';
    ctx.lineWidth = 1.6;
    ctx.lineCap = 'round';
    const fx = w * (0.15 + r() * 0.4), fy = h * (0.12 + r() * 0.15);
    for (let i = 0; i < 7; i++) {
      const x = fx + (r() - 0.3) * w * 0.18, y = fy + (r() - 0.5) * h * 0.12, s = h * (0.008 + r() * 0.01);
      ctx.beginPath();
      ctx.moveTo(x - s * 1.6, y - s * 0.4);
      ctx.quadraticCurveTo(x - s * 0.6, y - s * 1.1, x, y);
      ctx.quadraticCurveTo(x + s * 0.6, y - s * 1.1, x + s * 1.6, y - s * 0.4);
      ctx.stroke();
    }
  }

  // One streak across a quiet night sky.
  function shootingStar(ctx, w, h, r) {
    const x = w * (0.1 + r() * 0.4), y = h * (0.06 + r() * 0.14), len = w * 0.16;
    const g = ctx.createLinearGradient(x, y, x + len, y + len * 0.28);
    g.addColorStop(0, 'rgba(255,255,255,0)');
    g.addColorStop(1, 'rgba(255,255,255,0.9)');
    ctx.strokeStyle = g;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + len, y + len * 0.28);
    ctx.stroke();
  }

  // Flowers in the grass up front, smaller towards the back, and fireflies over them.
  function bloom(ctx, w, h, r) {
    const colours = ['#ffb3d1', '#ffffff', '#ffe066', '#c9a7ff', '#ff8fa3', '#9fd8ff'];
    for (let i = 0; i < 340; i++) {
      const depth = Math.pow(r(), 0.6), x = r() * w, y = h * (0.7 + depth * 0.3), s = 1.6 + depth * 7.5;
      ctx.strokeStyle = 'rgba(40,110,60,0.8)';
      ctx.lineWidth = Math.max(1, s * 0.3);
      ctx.beginPath();
      ctx.moveTo(x, y + s * 3);
      ctx.lineTo(x + (r() - 0.5) * s, y);
      ctx.stroke();
      const c = colours[Math.floor(r() * colours.length)];
      ctx.fillStyle = c;
      for (let k = 0; k < 5; k++) {
        const a = k / 5 * Math.PI * 2;
        ctx.beginPath();
        ctx.arc(x + Math.cos(a) * s * 0.7, y + Math.sin(a) * s * 0.7, s * 0.55, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.fillStyle = '#ffd23a';
      ctx.beginPath();
      ctx.arc(x, y, s * 0.4, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 40; i++) {
      const x = r() * w, y = h * (0.45 + r() * 0.35), s = 1 + r() * 2;
      const g = ctx.createRadialGradient(x, y, 0, x, y, s * 5);
      g.addColorStop(0, 'rgba(230,255,150,0.8)');
      g.addColorStop(1, 'rgba(230,255,150,0)');
      ctx.fillStyle = g;
      ctx.fillRect(x - s * 5, y - s * 5, s * 10, s * 10);
    }
    ctx.restore();
  }

  /* Scenes for Home cards. Three per level, the third being the mountains above, so a row of cards does not repeat.
     Focal points sit right of centre, because the card's text covers the lower left. */

  function linear(ctx, x0, y0, x1, y1, stops) {
    const g = ctx.createLinearGradient(x0, y0, x1, y1);
    stops.forEach(function (s) { g.addColorStop(s[0], s[1]); });
    return g;
  }
  function sky(ctx, w, h, stops) { ctx.fillStyle = linear(ctx, 0, 0, 0, h, stops); ctx.fillRect(0, 0, w, h); }
  function stars(ctx, w, h, r, count, depth) {
    for (let i = 0; i < count; i++) {
      const s = r() < 0.06 ? 1.8 : 1;
      ctx.fillStyle = 'rgba(255,255,255,' + (0.15 + r() * 0.6) + ')';
      ctx.fillRect(r() * w, r() * r() * h * depth, s, s);
    }
  }
  // A sun or moon with its halo.
  function orb(ctx, x, y, rad, core, edge, spread, strength) {
    const halo = ctx.createRadialGradient(x, y, rad * 0.5, x, y, rad * spread);
    halo.addColorStop(0, alpha(edge, strength));
    halo.addColorStop(0.35, alpha(edge, strength * 0.25));
    halo.addColorStop(1, alpha(edge, 0));
    ctx.fillStyle = halo;
    ctx.fillRect(x - rad * spread, y - rad * spread, rad * spread * 2, rad * spread * 2);
    const disc = ctx.createRadialGradient(x - rad * 0.3, y - rad * 0.3, rad * 0.1, x, y, rad);
    disc.addColorStop(0, core);
    disc.addColorStop(1, edge);
    ctx.fillStyle = disc;
    ctx.beginPath();
    ctx.arc(x, y, rad, 0, Math.PI * 2);
    ctx.fill();
  }
  // Clouds or smoke: soft blobs drawn small and scaled up, which blurs them.
  function clouds(ctx, w, h, r, color, strength, top, bottom, count) {
    const low = document.createElement('canvas');
    low.width = Math.ceil(w / 6); low.height = Math.ceil(h / 6);
    const lx = low.getContext('2d');
    for (let i = 0; i < count; i++) {
      const x = r() * low.width, y = low.height * (top + r() * (bottom - top)), rad = low.width * (0.04 + r() * 0.12);
      const g = lx.createRadialGradient(x, y, 0, x, y, rad);
      g.addColorStop(0, alpha(color, strength * (0.4 + r() * 0.6)));
      g.addColorStop(1, alpha(color, 0));
      lx.fillStyle = g;
      lx.fillRect(x - rad, y - rad, rad * 2, rad * 2);
    }
    ctx.save();
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(low, 0, 0, w, h);
    ctx.restore();
  }
  // Hills, dunes or ground from noise. Gives back the height at any x, so trees and fires can stand on it.
  function ground(ctx, w, h, n, off, baseY, amp, freq, sharp, fill) {
    const step = Math.max(2, Math.round(w / 400)), ys = [];
    for (let x = 0; x <= w + step; x += step) {
      const v = n(x / w * freq + off, 4);
      ys.push(baseY - (sharp ? Math.pow(1 - Math.abs(2 * v - 1), sharp) : v) * amp);
    }
    ctx.beginPath();
    ys.forEach(function (y, j) { if (j) ctx.lineTo(j * step, y); else ctx.moveTo(0, y); });
    ctx.lineTo(w + step, h); ctx.lineTo(0, h); ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
    return function (x) { return ys[Math.min(ys.length - 1, Math.max(0, Math.round(x / step)))]; };
  }
  function pine(ctx, x, base, height, color) {
    const width = height * 0.42;
    ctx.fillStyle = color;
    ctx.fillRect(x - height * 0.025, base - height * 0.15, height * 0.05, height * 0.16);
    for (let k = 0; k < 4; k++) {
      const bottom = base - height * (0.1 + k * 0.2), half = width * (1 - k * 0.2) / 2;
      ctx.beginPath();
      ctx.moveTo(x, bottom - height * 0.38);
      ctx.lineTo(x + half, bottom);
      ctx.lineTo(x - half, bottom);
      ctx.closePath();
      ctx.fill();
    }
  }
  function leafTree(ctx, x, base, size, dark, light, r) {
    ctx.fillStyle = dark;
    ctx.fillRect(x - size * 0.04, base - size * 0.5, size * 0.08, size * 0.5);
    for (let k = 0; k < 8; k++) {
      const bx = x + (r() - 0.5) * size * 0.6, by = base - size * (0.6 + r() * 0.4), br = size * (0.2 + r() * 0.14);
      const g = ctx.createRadialGradient(bx - br * 0.3, by - br * 0.4, br * 0.1, bx, by, br);
      g.addColorStop(0, light);
      g.addColorStop(1, dark);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(bx, by, br, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  // Glowing dots: embers, sparks, spray. Denser towards the bottom.
  function sparks(ctx, w, h, r, count, top, color, size) {
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < count; i++) {
      const x = r() * w, y = h * (top + Math.pow(r(), 0.7) * (1 - top)), s = 0.8 + r() * size;
      const g = ctx.createRadialGradient(x, y, 0, x, y, s * 4);
      g.addColorStop(0, color(r));
      g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g;
      ctx.fillRect(x - s * 4, y - s * 4, s * 8, s * 8);
    }
    ctx.restore();
  }
  const ember = function (r) { return 'rgba(255,' + Math.round(140 + r() * 100) + ',60,0.9)'; };
  function forkBolt(ctx, w, r, x, y, len, width, depth) {
    const pts = [[x, y]];
    for (let s = 0; s < 14; s++) { x += (r() - 0.5) * w * 0.035; y += len / 14; pts.push([x, y]); }
    [[26, 'rgba(255,120,90,0.14)'], [10, 'rgba(255,200,190,0.35)'], [width, 'rgba(255,255,255,1)']].forEach(function (pass) {
      ctx.beginPath();
      pts.forEach(function (pt, j) { if (j) ctx.lineTo(pt[0], pt[1]); else ctx.moveTo(pt[0], pt[1]); });
      ctx.lineWidth = pass[0];
      ctx.strokeStyle = pass[1];
      ctx.lineJoin = 'round';
      ctx.stroke();
    });
    if (depth < 2) for (let b = 0; b < 2; b++) { const at = pts[3 + Math.floor(r() * 8)]; forkBolt(ctx, w, r, at[0], at[1], len * 0.45, width * 0.6, depth + 1); }
  }
  function flame(ctx, x, base, height, r) {
    const wide = height * (0.22 + r() * 0.15), lean = (r() - 0.5) * height * 0.3;
    ctx.fillStyle = linear(ctx, x, base, x, base - height, [[0, 'rgba(255,240,170,0.95)'], [0.4, 'rgba(255,150,40,0.85)'], [1, 'rgba(255,60,10,0)']]);
    ctx.beginPath();
    ctx.moveTo(x - wide, base);
    ctx.quadraticCurveTo(x - wide * 0.9, base - height * 0.5, x + lean, base - height);
    ctx.quadraticCurveTo(x + wide * 0.9, base - height * 0.5, x + wide, base);
    ctx.closePath();
    ctx.fill();
  }
  function flowers(ctx, w, h, r, count, top) {
    const colours = ['#ffb3d1', '#ffffff', '#ffe066', '#c9a7ff', '#ff8fa3', '#9fd8ff'];
    for (let i = 0; i < count; i++) {
      const depth = Math.pow(r(), 0.6), x = r() * w, y = h * (top + depth * (1 - top)), s = 1.6 + depth * 7;
      ctx.strokeStyle = 'rgba(40,110,60,0.8)';
      ctx.lineWidth = Math.max(1, s * 0.3);
      ctx.beginPath();
      ctx.moveTo(x, y + s * 3);
      ctx.lineTo(x + (r() - 0.5) * s, y);
      ctx.stroke();
      ctx.fillStyle = colours[Math.floor(r() * colours.length)];
      for (let k = 0; k < 5; k++) {
        const a = k / 5 * Math.PI * 2;
        ctx.beginPath();
        ctx.arc(x + Math.cos(a) * s * 0.7, y + Math.sin(a) * s * 0.7, s * 0.55, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.fillStyle = '#ffd23a';
      ctx.beginPath();
      ctx.arc(x, y, s * 0.4, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  function butterfly(ctx, x, y, s, color) {
    ctx.fillStyle = color;
    [-1, 1].forEach(function (side) {
      ctx.beginPath();
      ctx.ellipse(x + side * s * 0.55, y - s * 0.2, s * 0.55, s * 0.4, side * 0.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.ellipse(x + side * s * 0.4, y + s * 0.35, s * 0.35, s * 0.28, -side * 0.4, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.fillStyle = '#2a2a2a';
    ctx.fillRect(x - s * 0.06, y - s * 0.5, s * 0.12, s * 1.1);
  }

  // Red: an eruption. Ash climbs out of the crater with lightning in it, lava runs down, bombs fly.
  function volcano(ctx, w, h, r, n) {
    sky(ctx, w, h, [[0, '#160202'], [0.4, '#4e0906'], [0.7, '#a41f0a'], [1, '#ff6a1a']]);
    stars(ctx, w, h, r, 30, 0.25);
    const cx = w * (0.6 + r() * 0.14), peak = h * (0.3 + r() * 0.05), base = h * 0.9, half = w * (0.36 + r() * 0.08);
    for (let k = 0; k < 30; k++) {
      const t = k / 29, px = cx + (n(t * 2 + 3, 2) - 0.5) * w * 0.3 * t + t * w * 0.06, py = peak - t * h * 0.3, rad = h * (0.05 + t * 0.15);
      const g = ctx.createRadialGradient(px, py, 0, px, py, rad);
      // Grey-brown ash, so the column stands out against the dark sky above it.
      g.addColorStop(0, 'rgba(' + Math.round(110 - t * 30) + ',' + Math.round(58 - t * 14) + ',' + Math.round(48 - t * 10) + ',' + (0.8 - t * 0.25) + ')');
      g.addColorStop(1, 'rgba(60,30,26,0)');
      ctx.fillStyle = g;
      ctx.fillRect(px - rad, py - rad, rad * 2, rad * 2);
    }
    for (let b = 0; b < 2; b++) forkBolt(ctx, w, r, cx + (r() - 0.5) * w * 0.2, peak - h * (0.22 + r() * 0.15), h * 0.18, 2.4, 1);
    ground(ctx, w, h, n, 11, h * 0.8, h * 0.1, 3, 1.5, '#2a0606');
    ctx.fillStyle = linear(ctx, 0, peak, 0, base, [[0, '#3a0b08'], [1, '#090202']]);
    ctx.beginPath();
    ctx.moveTo(cx - half, base + 2);
    ctx.quadraticCurveTo(cx - half * 0.3, base - (base - peak) * 0.3, cx - w * 0.04, peak);
    ctx.lineTo(cx + w * 0.04, peak);
    ctx.quadraticCurveTo(cx + half * 0.3, base - (base - peak) * 0.3, cx + half, base + 2);
    ctx.closePath();
    ctx.fill();
    const crater = ctx.createRadialGradient(cx, peak, 0, cx, peak, w * 0.12);
    crater.addColorStop(0, 'rgba(255,140,40,0.9)');
    crater.addColorStop(1, 'rgba(255,60,10,0)');
    ctx.fillStyle = crater;
    ctx.fillRect(cx - w * 0.12, peak - w * 0.12, w * 0.24, w * 0.24);
    ctx.save();
    ctx.shadowColor = '#ff6a00';
    ctx.shadowBlur = 18;
    ctx.lineCap = 'round';
    for (let k = 0; k < 6; k++) {
      let x = cx + (r() - 0.5) * w * 0.06, y = peak + 2;
      const drift = (0.2 + r() * 0.8) * (r() < 0.5 ? -1 : 1);
      ctx.beginPath();
      ctx.moveTo(x, y);
      for (let s = 0; s < 24; s++) { y += (base - peak) / 24; x += drift * w * 0.006 + (n(s * 0.4 + k * 9, 2) - 0.5) * w * 0.012; ctx.lineTo(x, y); }
      ctx.strokeStyle = k % 2 ? '#ffb020' : '#ff6a10';
      ctx.lineWidth = 2 + r() * 4;
      ctx.stroke();
    }
    ctx.restore();
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 160; i++) {
      const a = -Math.PI / 2 + (r() - 0.5) * 1.3, v = h * (0.15 + r() * 0.3), t = Math.sqrt(r()), s = 1 + r() * 2.5;
      const x = cx + Math.cos(a) * v * t * 1.2, y = peak + Math.sin(a) * v * t + h * 0.35 * t * t;
      const g = ctx.createRadialGradient(x, y, 0, x, y, s * 4);
      g.addColorStop(0, 'rgba(255,200,80,0.9)');
      g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g;
      ctx.fillRect(x - s * 4, y - s * 4, s * 8, s * 8);
    }
    ctx.restore();
    ground(ctx, w, h, n, 23, base + h * 0.04, h * 0.03, 2, 0, linear(ctx, 0, base, 0, h, [[0, '#140303'], [1, '#030000']]));
    ctx.save();
    ctx.shadowColor = '#ff5a00';
    ctx.shadowBlur = 10;
    ctx.strokeStyle = 'rgba(255,120,30,0.8)';
    ctx.lineWidth = 1.5;
    for (let k = 0; k < 9; k++) {
      let x = r() * w, y = base + h * 0.05 + r() * (h - base) * 0.8;
      ctx.beginPath();
      ctx.moveTo(x, y);
      for (let s = 0; s < 6; s++) { x += (r() - 0.5) * w * 0.04; y += (r() - 0.3) * h * 0.02; ctx.lineTo(x, y); }
      ctx.stroke();
    }
    ctx.restore();
    sparks(ctx, w, h, r, 120, 0.1, ember, 2.2);
  }

  // Red: a storm at sea. Black clouds lit red, lightning into the water, waves building up front, rain.
  function stormSea(ctx, w, h, r, n) {
    const y0 = h * 0.56;
    ctx.fillStyle = linear(ctx, 0, 0, 0, y0, [[0, '#050000'], [0.55, '#3a0505'], [1, '#c22a0e']]);
    ctx.fillRect(0, 0, w, y0);
    clouds(ctx, w, h, r, '#140202', 0.9, 0, 0.42, 70);
    clouds(ctx, w, h, r, '#ff3a1a', 0.25, 0.3, 0.5, 30);
    const xs = [], count = 2 + Math.floor(r() * 2);
    for (let b = 0; b < count; b++) { const x = w * (0.25 + r() * 0.7); xs.push(x); forkBolt(ctx, w, r, x, 0, y0, 3.4, 0); }
    ctx.fillStyle = linear(ctx, 0, y0, 0, h, [[0, '#3a0806'], [1, '#050000']]);
    ctx.fillRect(0, y0, w, h - y0);
    xs.forEach(function (x) {
      ctx.save();
      ctx.translate(x, y0);
      ctx.scale(1, 0.3);
      const g = ctx.createRadialGradient(0, 0, 0, 0, 0, w * 0.22);
      g.addColorStop(0, 'rgba(255,200,180,0.45)');
      g.addColorStop(1, 'rgba(255,80,40,0)');
      ctx.fillStyle = g;
      ctx.fillRect(-w * 0.22, -w * 0.22, w * 0.44, w * 0.44);
      ctx.restore();
    });
    const step = Math.max(3, Math.round(w / 300));
    for (let i = 0; i < 16; i++) {
      const t = i / 15, y = y0 + Math.pow(t, 1.7) * (h - y0) * 1.02, amp = h * (0.004 + t * t * 0.07), off = r() * 100, ys = [];
      for (let x = 0; x <= w + step; x += step) { const v = n(x / w * (14 - t * 9) + off, 3); ys.push(y - Math.pow(1 - Math.abs(2 * v - 1), 2.2) * amp); }
      const line = function () { ctx.beginPath(); ys.forEach(function (yy, j) { if (j) ctx.lineTo(j * step, yy); else ctx.moveTo(0, yy); }); };
      line();
      ctx.lineTo(w + step, h); ctx.lineTo(0, h); ctx.closePath();
      ctx.fillStyle = linear(ctx, 0, y - amp, 0, y + h * 0.08, [[0, mix('#5a0c08', '#1a0302', t)], [1, mix('#1a0302', '#030000', t)]]);
      ctx.fill();
      line();
      ctx.strokeStyle = 'rgba(255,' + Math.round(140 + 60 * (1 - t)) + ',110,' + (0.18 + t * 0.3) + ')';
      ctx.lineWidth = 1 + t * 2;
      ctx.stroke();
    }
    sparks(ctx, w, h, r, 90, 0.7, function () { return 'rgba(255,220,200,0.5)'; }, 1.6);
    ctx.strokeStyle = 'rgba(255,200,190,0.12)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < 260; i++) { const x = r() * w * 1.2, y = r() * h, l = h * (0.03 + r() * 0.05); ctx.moveTo(x, y); ctx.lineTo(x - l * 0.35, y + l); }
    ctx.stroke();
  }

  // Orange: desert dunes under a huge low sun, the air shimmering.
  function dunes(ctx, w, h, r, n) {
    const y0 = h * 0.6;
    sky(ctx, w, h, [[0, '#1a0703'], [0.35, '#6a2209'], [0.55, '#d9611c'], [0.62, '#ffb15a'], [1, '#ffb15a']]);
    stars(ctx, w, h, r, 40, 0.25);
    orb(ctx, w * (0.62 + r() * 0.2), y0 - h * 0.06, h * 0.11, '#fff1c8', '#ff9a3c', 5, 0.6);
    clouds(ctx, w, h, r, '#ff7a2a', 0.25, 0.15, 0.45, 18);
    ctx.strokeStyle = 'rgba(255,220,160,0.12)';
    ctx.lineWidth = 1;
    for (let i = 0; i < 10; i++) {
      const y = y0 - h * 0.03 + i * h * 0.006;
      ctx.beginPath();
      for (let x = 0; x <= w; x += 8) { const yy = y + Math.sin(x / w * 40 + i) * h * 0.002; if (x) ctx.lineTo(x, yy); else ctx.moveTo(x, yy); }
      ctx.stroke();
    }
    const tones = [['#c4581f', '#7a2e0e'], ['#a8471a', '#5e220a'], ['#8a3814', '#431606'], ['#6a2a0e', '#2a0c03'], ['#4a1c08', '#160501']];
    tones.forEach(function (c, i) {
      const t = i / (tones.length - 1), base = h * (0.62 + t * t * 0.36), amp = h * (0.05 + t * 0.07);
      const p1 = r() * 6, p2 = r() * 6, f1 = 1.2 + r() * 1.5, f2 = 3 + r() * 2, ys = [];
      for (let x = 0; x <= w + 4; x += 4) { const u = x / w * Math.PI * 2; ys.push(base - (Math.sin(u * f1 + p1) * 0.6 + Math.sin(u * f2 + p2) * 0.25 + n(x / w * 3 + i * 7, 2) * 0.5) * amp); }
      const line = function () { ctx.beginPath(); ys.forEach(function (y, j) { if (j) ctx.lineTo(j * 4, y); else ctx.moveTo(0, y); }); };
      line();
      ctx.lineTo(w + 4, h); ctx.lineTo(0, h); ctx.closePath();
      ctx.fillStyle = linear(ctx, 0, base - amp, 0, base + h * 0.15, [[0, c[0]], [1, c[1]]]);
      ctx.fill();
      line();
      ctx.strokeStyle = 'rgba(255,214,150,' + (0.5 - t * 0.3) + ')';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    });
    ctx.strokeStyle = 'rgba(255,190,130,0.12)';
    for (let k = 0; k < 14; k++) {
      const y = h * 0.9 + k * h * 0.008, p = r() * 6;
      ctx.beginPath();
      for (let x = 0; x <= w; x += 6) { const yy = y + Math.sin(x / w * 18 + p) * h * 0.004; if (x) ctx.lineTo(x, yy); else ctx.moveTo(x, yy); }
      ctx.stroke();
    }
  }

  // Orange: a forest fire. Smoke over a red sun, flames on the far ridge, rows of pines in front of the glow.
  function wildfire(ctx, w, h, r, n) {
    sky(ctx, w, h, [[0, '#120604'], [0.4, '#4a1808'], [0.62, '#b8461a'], [0.72, '#ff8a3a'], [1, '#ff8a3a']]);
    orb(ctx, w * (0.66 + r() * 0.18), h * (0.26 + r() * 0.08), h * 0.06, '#ffd2a0', '#ff5a2a', 4, 0.45);
    clouds(ctx, w, h, r, '#2a1810', 0.7, 0.05, 0.55, 40);
    const far = ground(ctx, w, h, n, 3, h * 0.66, h * 0.1, 2.2, 1.2, '#5a2210');
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.fillStyle = linear(ctx, 0, h * 0.45, 0, h * 0.7, [[0, 'rgba(255,90,20,0)'], [1, 'rgba(255,120,30,0.45)']]);
    ctx.fillRect(0, h * 0.45, w, h * 0.25);
    for (let i = 0; i < 70; i++) { const x = r() * w; flame(ctx, x, far(x) + 2, h * (0.02 + r() * 0.07), r); }
    ctx.restore();
    [[0.72, 0.09, '#2a0c05', 40], [0.82, 0.16, '#160602', 26], [0.95, 0.3, '#060100', 12]].forEach(function (row, k) {
      const line = ground(ctx, w, h, n, 20 + k * 5, h * row[0], h * 0.04, 2, 0, row[2]);
      for (let i = 0; i < row[3]; i++) { const x = r() * w; pine(ctx, x, line(x) + 2, h * row[1] * (0.6 + r() * 0.6), row[2]); }
    });
    sparks(ctx, w, h, r, 110, 0.15, ember, 2.2);
  }

  // Yellow: a wheat field in the afternoon sun, sunflowers up front, birds overhead.
  function wheat(ctx, w, h, r, n) {
    sky(ctx, w, h, [[0, '#3a2a0c'], [0.35, '#a87a1c'], [0.6, '#ffd36a'], [1, '#fff1c4']]);
    orb(ctx, w * (0.7 + r() * 0.15), h * (0.2 + r() * 0.08), h * 0.07, '#fffbe6', '#ffd23a', 6, 0.55);
    clouds(ctx, w, h, r, '#fff4d0', 0.28, 0.05, 0.4, 16);
    birds(ctx, w, h, r);
    ground(ctx, w, h, n, 5, h * 0.6, h * 0.08, 2, 0, '#b49a3c');
    ground(ctx, w, h, n, 9, h * 0.65, h * 0.06, 2.5, 0, '#8f7424');
    ctx.fillStyle = linear(ctx, 0, h * 0.66, 0, h, [[0, '#c99a24'], [1, '#6a4a0c']]);
    ctx.fillRect(0, h * 0.66, w, h * 0.34);
    for (let i = 0; i < 1100; i++) {
      const d = Math.pow(r(), 0.8), x = r() * w, y = h * (0.66 + d * 0.34), len = h * (0.008 + d * 0.06);
      ctx.strokeStyle = mix('#e8c050', '#7a5410', r() * 0.6);
      ctx.lineWidth = 0.6 + d * 1.6;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + (r() - 0.5) * len * 0.3, y - len);
      ctx.stroke();
      if (d > 0.3) {
        ctx.fillStyle = '#f2d06a';
        ctx.beginPath();
        ctx.ellipse(x, y - len, 1 + d * 1.5, 2 + d * 4, 0, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    const count = 5 + Math.floor(r() * 4);
    for (let i = 0; i < count; i++) sunflower(ctx, w * (0.55 + r() * 0.45), h * (0.78 + r() * 0.18), h * (0.045 + r() * 0.05));
  }
  function sunflower(ctx, x, y, size) {
    ctx.strokeStyle = '#3f6a1c';
    ctx.lineWidth = size * 0.12;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + size * 0.1, y + size * 3);
    ctx.stroke();
    for (let k = 0; k < 18; k++) {
      const a = k / 18 * Math.PI * 2;
      ctx.save();
      ctx.translate(x + Math.cos(a) * size * 0.75, y + Math.sin(a) * size * 0.75);
      ctx.rotate(a);
      ctx.fillStyle = k % 2 ? '#ffd23a' : '#f5b81e';
      ctx.beginPath();
      ctx.ellipse(0, 0, size * 0.45, size * 0.16, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
    const g = ctx.createRadialGradient(x, y, 0, x, y, size * 0.5);
    g.addColorStop(0, '#6a3a0a');
    g.addColorStop(1, '#2a1404');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(x, y, size * 0.5, 0, Math.PI * 2);
    ctx.fill();
  }

  // Yellow: a beach in the golden hour, sun glitter on the sea, a palm on the right.
  function beach(ctx, w, h, r, n) {
    const y0 = h * 0.56, shore = h * 0.8;
    sky(ctx, w, h, [[0, '#2a2a3a'], [0.3, '#8a6a3a'], [0.5, '#ffc45a'], [0.56, '#ffe6a8'], [1, '#ffe6a8']]);
    const sx = w * (0.58 + r() * 0.16);
    orb(ctx, sx, y0 - h * 0.08, h * 0.075, '#fffbe8', '#ffc040', 6, 0.6);
    clouds(ctx, w, h, r, '#fff0c8', 0.3, 0.08, 0.4, 14);
    ctx.fillStyle = linear(ctx, 0, y0, 0, shore, [[0, '#d9a542'], [0.4, '#7a7a5a'], [1, '#2a4a5a']]);
    ctx.fillRect(0, y0, w, shore - y0);
    for (let i = 0; i < 220; i++) {
      const d = Math.pow(r(), 0.7), y = y0 + d * (shore - y0), spread = w * (0.02 + d * 0.12);
      const x = sx + (r() - 0.5) * 2 * spread, l = w * (0.004 + d * 0.02);
      ctx.fillStyle = 'rgba(255,240,190,' + (0.35 + r() * 0.5) + ')';
      ctx.fillRect(x, y, l, 1 + d * 1.5);
    }
    ctx.strokeStyle = 'rgba(255,255,255,0.12)';
    ctx.lineWidth = 1;
    for (let k = 0; k < 14; k++) {
      const y = y0 + Math.pow(r(), 1.3) * (shore - y0), x = r() * w;
      ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + w * (0.05 + r() * 0.15), y); ctx.stroke();
    }
    const edge = [];
    for (let x = 0; x <= w + 6; x += 6) edge.push(shore + (n(x / w * 4 + 2, 3) - 0.5) * h * 0.03);
    const coast = function (dy) { ctx.beginPath(); edge.forEach(function (y, j) { if (j) ctx.lineTo(j * 6, y + dy); else ctx.moveTo(0, y + dy); }); };
    coast(0);
    ctx.lineTo(w + 6, h); ctx.lineTo(0, h); ctx.closePath();
    ctx.fillStyle = linear(ctx, 0, shore, 0, h, [[0, '#e9c98e'], [1, '#a8783e']]);
    ctx.fill();
    coast(0);
    ctx.strokeStyle = 'rgba(255,255,255,0.7)';
    ctx.lineWidth = 2;
    ctx.stroke();
    coast(-h * 0.012);
    ctx.strokeStyle = 'rgba(255,255,255,0.25)';
    ctx.lineWidth = 1;
    ctx.stroke();
    palm(ctx, w * (0.86 + r() * 0.08), h * 1.02, h * 0.66, r);
  }
  function palm(ctx, x, base, height, r) {
    const topX = x - height * 0.25, topY = base - height;
    ctx.strokeStyle = '#2a1a0c';
    ctx.lineWidth = height * 0.035;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(x, base);
    ctx.quadraticCurveTo(x - height * 0.02, base - height * 0.6, topX, topY);
    ctx.stroke();
    ctx.fillStyle = '#1e2a12';
    for (let k = 0; k < 8; k++) {
      const a = -Math.PI + k / 7 * Math.PI + (r() - 0.5) * 0.3, len = height * (0.35 + r() * 0.15);
      const ex = topX + Math.cos(a) * len, ey = topY + Math.sin(a) * len * 0.5 + len * 0.35;
      const mx = topX + Math.cos(a) * len * 0.5, my = topY + Math.sin(a) * len * 0.5 - len * 0.1;
      ctx.beginPath();
      ctx.moveTo(topX, topY);
      ctx.quadraticCurveTo(mx, my - len * 0.08, ex, ey);
      ctx.quadraticCurveTo(mx, my + len * 0.08, topX, topY);
      ctx.fill();
    }
  }

  // Blue: a lake at night, the moon's road on the water, pines on the shore mirrored below.
  function nightLake(ctx, w, h, r, n) {
    const y0 = h * 0.6;
    sky(ctx, w, h, [[0, '#01030b'], [0.45, '#061838'], [0.85, '#123f78'], [1, '#2a64a8']]);
    stars(ctx, w, h, r, 380, 0.6);
    clouds(ctx, w, h, r, '#4aa8ff', 0.18, 0.1, 0.35, 20);
    const mx = w * (0.6 + r() * 0.25), my = h * (0.16 + r() * 0.1);
    orb(ctx, mx, my, h * 0.055, '#ffffff', '#cfe6ff', 6, 0.4);
    shootingStar(ctx, w, h, r);
    ground(ctx, w, h, n, 4, y0 - h * 0.01, h * 0.14, 2.5, 1.4, '#0c2a52');
    ctx.fillStyle = linear(ctx, 0, y0, 0, h, [[0, '#123a6a'], [1, '#020814']]);
    ctx.fillRect(0, y0, w, h - y0);
    for (let i = 0; i < 140; i++) {
      const d = r(), y = y0 + d * (h - y0), half = w * (0.01 + d * 0.06) * r();
      ctx.fillStyle = 'rgba(220,236,255,' + (0.5 - d * 0.35) + ')';
      ctx.fillRect(mx - half, y, half * 2, 1 + d * 2);
    }
    ctx.strokeStyle = 'rgba(180,210,255,0.08)';
    ctx.lineWidth = 1;
    for (let k = 0; k < 30; k++) {
      const y = y0 + Math.pow(r(), 1.5) * (h - y0), x = r() * w;
      ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + w * (0.03 + r() * 0.1), y); ctx.stroke();
    }
    const shore = function (x0, x1, count) {
      for (let i = 0; i < count; i++) {
        const x = x0 + r() * (x1 - x0), tall = h * (0.08 + r() * 0.12);
        pine(ctx, x, y0 + 2, tall, '#020a18');
        ctx.save();
        ctx.globalAlpha = 0.35;
        ctx.translate(0, 2 * (y0 + 2));
        ctx.scale(1, -1);
        pine(ctx, x, y0 + 2, tall, '#020a18');
        ctx.restore();
      }
    };
    shore(-w * 0.02, w * 0.35, 26);
    shore(w * 0.82, w * 1.02, 10);
    ctx.fillStyle = linear(ctx, 0, y0 - h * 0.04, 0, y0 + h * 0.04, [[0, 'rgba(170,200,240,0)'], [0.5, 'rgba(170,200,240,0.18)'], [1, 'rgba(170,200,240,0)']]);
    ctx.fillRect(0, y0 - h * 0.04, w, h * 0.08);
  }

  // Blue: a city asleep. Three rows of towers, a few windows still lit, the river below reflecting them.
  function nightCity(ctx, w, h, r) {
    const y0 = h * 0.82;
    sky(ctx, w, h, [[0, '#020615'], [0.5, '#0a1d45'], [0.85, '#24508f'], [1, '#3a6fb0']]);
    stars(ctx, w, h, r, 200, 0.5);
    orb(ctx, w * (0.7 + r() * 0.2), h * (0.14 + r() * 0.08), h * 0.045, '#ffffff', '#cfe6ff', 6, 0.35);
    clouds(ctx, w, h, r, '#6aa8ff', 0.12, 0.2, 0.5, 14);
    [['#1a3a6a', 0.45, 0.1], ['#0d2246', 0.32, 0.25], ['#050c1e', 0.22, 0.45]].forEach(function (row) {
      const maxH = h * row[1];
      let x = -r() * w * 0.03;
      while (x < w) {
        const bw = w * (0.025 + r() * 0.05), bh = maxH * (0.35 + r() * 0.65) * (r() < 0.12 ? 1.4 : 1);
        ctx.fillStyle = row[0];
        ctx.fillRect(x, y0 - bh, bw, bh + 1);
        if (r() < 0.2) ctx.fillRect(x + bw * 0.45, y0 - bh - h * 0.03, bw * 0.08, h * 0.03);
        const cols = Math.max(2, Math.floor(bw / (w * 0.008))), rows = Math.floor(bh / (h * 0.022));
        for (let c = 0; c < cols; c++) {
          for (let k = 0; k < rows; k++) {
            if (r() >= row[2]) continue;
            ctx.fillStyle = r() < 0.7 ? 'rgba(255,214,140,0.85)' : 'rgba(190,225,255,0.8)';
            ctx.fillRect(x + bw * (0.12 + c * 0.76 / cols), y0 - bh + h * 0.012 + k * h * 0.022, Math.max(1, bw * 0.08), h * 0.008);
          }
        }
        x += bw + w * (0.002 + r() * 0.01);
      }
    });
    ctx.fillStyle = linear(ctx, 0, y0, 0, h, [[0, '#0a1a38'], [1, '#02060f']]);
    ctx.fillRect(0, y0, w, h - y0);
    for (let i = 0; i < 160; i++) {
      const x = r() * w, y = y0 + r() * (h - y0), l = h * (0.005 + r() * 0.03);
      ctx.fillStyle = 'rgba(255,214,140,' + (0.08 + r() * 0.25) + ')';
      ctx.fillRect(x, y, 1.5, l);
    }
    ctx.fillStyle = linear(ctx, 0, y0 - h * 0.03, 0, y0 + h * 0.02, [[0, 'rgba(150,190,240,0)'], [0.6, 'rgba(150,190,240,0.14)'], [1, 'rgba(150,190,240,0)']]);
    ctx.fillRect(0, y0 - h * 0.03, w, h * 0.05);
  }

  // Green: a spring meadow. Soft hills, a few round trees, flowers up front, butterflies.
  function meadow(ctx, w, h, r, n) {
    sky(ctx, w, h, [[0, '#1e5a78'], [0.5, '#6ab0b0'], [0.8, '#cfeccc'], [1, '#f2fbe6']]);
    orb(ctx, w * (0.7 + r() * 0.15), h * (0.18 + r() * 0.08), h * 0.06, '#fffdf0', '#fff1b0', 6, 0.5);
    clouds(ctx, w, h, r, '#ffffff', 0.35, 0.05, 0.4, 16);
    let mid = null;
    [['#7cc48a', 0.56, 0.1], ['#5aa86c', 0.64, 0.1], ['#3f8f54', 0.74, 0.09], ['#2a7240', 0.86, 0.08]].forEach(function (hl, i) {
      const line = ground(ctx, w, h, n, 30 + i * 4, h * hl[1], h * hl[2], 1.6, 0, hl[0]);
      if (i === 1) mid = line;
      if (i === 1) for (let k = 0; k < 6; k++) { const x = w * (0.4 + r() * 0.6); leafTree(ctx, x, mid(x) + 4, h * (0.08 + r() * 0.06), '#2a6a3a', '#7cc48a', r); }
    });
    flowers(ctx, w, h, r, 300, 0.76);
    const wings = ['#ffd23a', '#ff9ec4', '#ffffff', '#9fd8ff'];
    for (let i = 0; i < 7; i++) butterfly(ctx, w * (0.35 + r() * 0.65), h * (0.35 + r() * 0.4), h * (0.008 + r() * 0.01), wings[i % wings.length]);
  }

  // Green: a grove with sunbeams falling through it, big trees left and right, grass and flowers.
  function grove(ctx, w, h, r, n) {
    sky(ctx, w, h, [[0, '#2a5a3a'], [0.5, '#8ac890'], [1, '#eaf8d8']]);
    const sx = w * (0.75 + r() * 0.15), sy = -h * 0.05;
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    for (let k = 0; k < 7; k++) {
      const a = Math.PI * (0.58 + r() * 0.2), spread = 0.02 + r() * 0.04, len = h * 2;
      ctx.fillStyle = 'rgba(255,250,210,' + (0.05 + r() * 0.08) + ')';
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(sx + Math.cos(a - spread) * len, sy + Math.sin(a - spread) * len);
      ctx.lineTo(sx + Math.cos(a + spread) * len, sy + Math.sin(a + spread) * len);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
    const far = ground(ctx, w, h, n, 41, h * 0.62, h * 0.05, 2, 0, '#6aae76');
    for (let i = 0; i < 26; i++) { const x = r() * w; leafTree(ctx, x, far(x) + 4, h * (0.08 + r() * 0.05), '#4a8a58', '#a8dcae', r); }
    ground(ctx, w, h, n, 47, h * 0.72, h * 0.04, 2, 0, '#4a9a5a');
    leafTree(ctx, w * (0.02 + r() * 0.08), h * 1.02, h * 0.62, '#1f5a30', '#5aa86a', r);
    leafTree(ctx, w * (0.9 + r() * 0.08), h * 1.02, h * 0.7, '#1f5a30', '#5aa86a', r);
    ground(ctx, w, h, n, 53, h * 0.86, h * 0.03, 3, 0, '#3f8a4a');
    flowers(ctx, w, h, r, 220, 0.82);
    const wings = ['#ffd23a', '#ff9ec4', '#ffffff'];
    for (let i = 0; i < 5; i++) butterfly(ctx, w * (0.3 + r() * 0.6), h * (0.4 + r() * 0.35), h * (0.008 + r() * 0.008), wings[i % wings.length]);
  }

  // Null is the mountains, drawn in the level's colours.
  const MOTIFS = {
    critical: [volcano, stormSea, null],
    high: [dunes, wildfire, null],
    medium: [wheat, beach, null],
    low: [nightLake, nightCity, null],
    calm: [meadow, grove, null]
  };

  function fogOver(ctx, w, h, r, fog) {
    for (let k = 0; k < 7; k++) {
      const y = h * (0.42 + r() * 0.5), band = h * (0.1 + r() * 0.16);
      ctx.fillStyle = linear(ctx, 0, y - band, 0, y + band, [[0, 'rgba(190,200,215,0)'], [0.5, 'rgba(190,200,215,' + 0.17 * fog + ')'], [1, 'rgba(190,200,215,0)']]);
      ctx.fillRect(0, y - band, w, band * 2);
    }
  }
  function draw(cv, o) {
    const pool = MOTIFS[o.level];
    const motif = pool ? pool[hash((o.seed || 'x') + '#scene') % pool.length] : null;
    if (!motif) { paint(cv, o); return; }
    const ctx = cv.getContext('2d'), r = rng(hash(o.seed || 'x')), n = noiseFn(r);
    motif(ctx, cv.width, cv.height, r, n);
    if ((o.fog || 0) > 0.2) fogOver(ctx, cv.width, cv.height, r, o.fog);
    grain(ctx, cv.width, cv.height, r);
  }

  const cache = new Map();

  /* The same card keeps the same picture, so a data refresh never makes the scenery flicker. */
  function scene(o, width, height) {
    const key = [o.seed, o.kind, o.level || '', (o.heat || 0).toFixed(1), (o.fog || 0).toFixed(1), width, height].join('|');
    if (cache.has(key)) return cache.get(key);
    const cv = document.createElement('canvas');
    cv.width = width; cv.height = height;
    draw(cv, o);
    cache.set(key, cv);
    if (cache.size > 40) cache.delete(cache.keys().next().value);
    return cv;
  }

  window.Art = {
    scene: scene,
    accent: function (kind) { return (PALETTES[kind] || PALETTES.brain).accent; },
    // A Home card's colour: its urgency when it has one, otherwise its kind.
    tone: function (c) { const L = c && LEVELS[c.level]; return L ? L.pal.accent : (PALETTES[c && c.kind] || PALETTES.brain).accent; }
  };
})();
