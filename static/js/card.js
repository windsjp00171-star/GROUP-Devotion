// 金句圖卡：在瀏覽器端用 canvas 畫出「經文＋領受」的分享圖（D3 書芽品牌風）。
// 刻意做在前端：正式站是 gunicorn 沒有瀏覽器可以截圖，前端畫也順便離線可用、
// 用的是頁面已經載好的字型。經文用明體、領受用黑體，兩者視覺上分清楚——
// 神的話跟自己的話不混在一起。

const SPROUT_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">' +
  '<g transform="translate(256,256)">' +
  '<path d="M0 40 C-40 6 -108 4 -150 20 L-150 128 C-108 112 -40 114 0 148 Z" fill="#EBD9AE"/>' +
  '<path d="M0 40 C40 6 108 4 150 20 L150 128 C108 112 40 114 0 148 Z" fill="#F7EBCB"/>' +
  '<path d="M0 40 L0 148" stroke="#D8BE86" stroke-width="8" stroke-linecap="round"/>' +
  '<path d="M0 40 C0 0 0 -18 0 -44" stroke="#8AA26B" stroke-width="12" fill="none" stroke-linecap="round"/>' +
  '<path d="M0 -8 C-44 -14 -70 -54 -66 -86 C-30 -86 2 -58 0 -12 Z" fill="#9DBE72"/>' +
  '<path d="M0 -28 C44 -34 72 -74 68 -106 C30 -104 2 -74 0 -32 Z" fill="#B6D18C"/>' +
  '</g></svg>';

function loadSprout() {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(SPROUT_SVG);
  });
}

function wrapLines(ctx, text, font, maxWidth) {
  // 中文可以在任何字之間換行，逐字累積到超過寬度就斷。
  ctx.font = font;
  const lines = [];
  let cur = '';
  for (const ch of text) {
    if (ch === '\n') {
      lines.push(cur);
      cur = '';
      continue;
    }
    if (cur && ctx.measureText(cur + ch).width > maxWidth) {
      lines.push(cur);
      cur = ch;
    } else {
      cur += ch;
    }
  }
  if (cur) lines.push(cur);
  return lines;
}

function drawCenteredText(ctx, text, cx, y, font, color, letterSpacing) {
  ctx.font = font;
  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'alphabetic';
  if (letterSpacing && 'letterSpacing' in ctx) {
    ctx.letterSpacing = letterSpacing + 'px';
    ctx.fillText(text, cx, y);
    ctx.letterSpacing = '0px';
  } else {
    ctx.fillText(text, cx, y);
  }
}

async function renderCard(canvas, data, fmt) {
  const W = 1080;
  const H = fmt === 'portrait' ? 1920 : 1080;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');
  const cx = W / 2;
  const PAD = 130;
  const maxW = W - PAD * 2;

  // 先確定字型載好，不然 canvas 會用系統 fallback（明體變成黑體就不美了）。
  const sample = (data.verse || '') + (data.note || '') + (data.reference || '') + '我的領受恩典少年一起讀這段';
  try {
    await Promise.all([
      document.fonts.load("600 52px 'Noto Serif TC'", sample),
      document.fonts.load("500 40px 'Noto Sans TC'", sample),
      document.fonts.load("600 28px 'Noto Sans TC'", sample),
    ]);
    await document.fonts.ready;
  } catch (e) {
    /* 載不到就用 fallback 畫，總比不能畫好 */
  }

  const sprout = await loadSprout();

  // 背景：暖色放射漸層（D3）
  const g = ctx.createRadialGradient(cx, H * 0.34, 80, cx, H * 0.34, H * 0.92);
  g.addColorStop(0, '#FEF8EA');
  g.addColorStop(1, '#F1D9BB');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);

  // 版面元素尺寸
  const logo = 150;
  const verseFont = "600 52px 'Noto Serif TC'";
  const verseLH = 88;
  const noteFont = "500 40px 'Noto Sans TC'";
  const noteLH = 68;

  const verseText = data.verse ? '「' + data.verse + '」' : '';
  const verseLines = verseText ? wrapLines(ctx, verseText, verseFont, maxW) : [];
  const noteLines = data.note ? wrapLines(ctx, data.note, noteFont, maxW) : [];

  // 量整個內容區塊的高度，好垂直置中
  let blockH = 0;
  blockH += logo + 48;
  if (verseLines.length) blockH += verseLines.length * verseLH + 30;
  blockH += 34; // reference
  if (noteLines.length) blockH += 40 /*divider+label gap*/ + 30 + 12 + noteLines.length * noteLH;

  let y = Math.max((H - blockH) / 2, 150) + logo; // 目前 y = logo 底部基準

  // 1) sprout logo
  if (sprout) ctx.drawImage(sprout, cx - logo / 2, y - logo, logo, logo);
  y += 48;

  // 2) 經文（明體）
  if (verseLines.length) {
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.font = verseFont;
    ctx.fillStyle = '#463A2B';
    verseLines.forEach((ln) => {
      ctx.fillText(ln, cx, y);
      y += verseLH;
    });
    y += 30;
  }

  // 3) 出處
  drawCenteredText(ctx, data.reference, cx, y + 28, "600 26px 'Noto Sans TC'", '#A98A55', 4);
  y += 34;

  // 4) 領受（黑體，跟經文分清楚）
  if (noteLines.length) {
    y += 26;
    // 細分隔線
    ctx.strokeStyle = '#D8BE86';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cx - 28, y);
    ctx.lineTo(cx + 28, y);
    ctx.stroke();
    y += 34;
    drawCenteredText(ctx, '我的領受', cx, y, "600 24px 'Noto Sans TC'", '#B0916A', 3);
    y += 40;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.font = noteFont;
    ctx.fillStyle = '#5A4B38';
    noteLines.forEach((ln) => {
      ctx.fillText(ln, cx, y);
      y += noteLH;
    });
  }

  // 5) 品牌頁腳
  drawCenteredText(ctx, '恩典少年 · 一起讀這段', cx, H - 68, "500 24px 'Noto Sans TC'", '#B3A488', 3);
}

function initCardMaker() {
  const canvas = document.getElementById('card-canvas');
  const dataEl = document.getElementById('card-data');
  if (!canvas || !dataEl) return;

  let data;
  try {
    data = JSON.parse(dataEl.textContent);
  } catch (e) {
    return;
  }

  let fmt = 'square';

  function redraw() {
    renderCard(canvas, data, fmt);
  }

  document.querySelectorAll('[data-fmt]').forEach((btn) => {
    btn.addEventListener('click', () => {
      fmt = btn.dataset.fmt;
      document.querySelectorAll('[data-fmt]').forEach((b) => b.classList.toggle('card-fmt--active', b === btn));
      redraw();
    });
  });

  const filename = () => 'devotion-' + (fmt === 'portrait' ? 'story' : 'post') + '.png';

  const dl = document.getElementById('card-download');
  if (dl) {
    dl.addEventListener('click', () => {
      canvas.toBlob((blob) => {
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename();
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }, 'image/png');
    });
  }

  const share = document.getElementById('card-share');
  if (share) {
    // 手機上支援 Web Share 才顯示「分享」，可以直接丟去 LINE／IG。
    if (navigator.canShare && navigator.canShare({ files: [new File([], 'x.png')] })) {
      share.hidden = false;
      share.addEventListener('click', () => {
        canvas.toBlob(async (blob) => {
          if (!blob) return;
          const file = new File([blob], filename(), { type: 'image/png' });
          try {
            await navigator.share({ files: [file], title: '恩典少年 · 一起讀這段' });
          } catch (e) {
            /* 使用者取消分享，什麼都不用做 */
          }
        }, 'image/png');
      });
    }
  }

  redraw();
}

document.addEventListener('DOMContentLoaded', initCardMaker);
