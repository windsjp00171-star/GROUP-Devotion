// 聚焦式導覽：畫面上標了 data-tour-step 的元素，照它們在 DOM 裡出現的順序
// 依序打光說明（data-tour-text 是那一步的文字）。第一次進到這個畫面會自動
// 開始，看過一次之後存在瀏覽器本機（localStorage），不會每次都跳出來；
// 右上角「？」可以隨時重看。

document.addEventListener('DOMContentLoaded', () => {
  const steps = Array.from(document.querySelectorAll('[data-tour-step]'));
  const tourBtn = document.querySelector('[data-tour]');
  if (!steps.length || !tourBtn) return;

  const frame = document.querySelector('[data-tour-target]');
  const screenKey = frame ? frame.dataset.tourTarget : 'home';
  const storageKey = `gd_tour_seen_${screenKey}`;

  const overlay = document.createElement('div');
  overlay.className = 'tour-overlay';
  overlay.hidden = true;

  const spotlight = document.createElement('div');
  spotlight.className = 'tour-spotlight';
  overlay.appendChild(spotlight);

  const callout = document.createElement('div');
  callout.className = 'tour-callout';
  callout.innerHTML =
    '<p class="tour-callout__text"></p>' +
    '<div class="tour-callout__footer">' +
    '<button type="button" class="tour-callout__skip">跳過</button>' +
    '<div class="tour-callout__dots"></div>' +
    '<button type="button" class="tour-callout__next">下一步</button>' +
    '</div>';
  overlay.appendChild(callout);
  document.body.appendChild(overlay);

  const textEl = callout.querySelector('.tour-callout__text');
  const nextBtn = callout.querySelector('.tour-callout__next');
  const skipBtn = callout.querySelector('.tour-callout__skip');
  const dotsEl = callout.querySelector('.tour-callout__dots');

  let index = 0;

  // 頁面現在比較長，捲到很下面的步驟需要的捲動時間比較久，用固定延遲會抓到
  // 捲動途中的座標。改成輪詢 scrollY，連續幾個影格沒再變動才視為捲動完成。
  function waitForScrollSettle(callback) {
    let lastY = window.scrollY;
    let stableFrames = 0;
    let totalFrames = 0;

    function check() {
      totalFrames += 1;
      const currentY = window.scrollY;
      if (Math.abs(currentY - lastY) < 1) {
        stableFrames += 1;
      } else {
        stableFrames = 0;
      }
      lastY = currentY;

      if (stableFrames >= 4 || totalFrames > 120) {
        callback();
        return;
      }
      requestAnimationFrame(check);
    }

    requestAnimationFrame(check);
  }

  // spotlight／callout 都用 position: fixed（相對視窗，不是相對頁面），
  // 所以量位置直接用 getBoundingClientRect() 就好，不用再加 scrollY/scrollX。
  function positionOn(el) {
    const rect = el.getBoundingClientRect();
    const pad = 8;
    const margin = 8; // 框跟畫面邊緣至少留這麼多，不要貼齊或爆出去
    const viewportWidth = document.documentElement.clientWidth;
    const viewportHeight = document.documentElement.clientHeight;

    // 關鍵修正：把打光的框「夾」在畫面範圍內。目標比整個畫面還高（例如後台那些很長的
    // 表單）時，rect.top 會是負的、rect.bottom 會超出畫面，直接拿原始值去畫，框跟說明卡
    // 都會爆到畫面外、看起來怪怪的一大塊。改成先算出「可見的那一段」再畫。
    const boxTop = Math.max(margin, rect.top - pad);
    const boxBottom = Math.min(viewportHeight - margin, rect.bottom + pad);
    const boxLeft = Math.max(margin, rect.left - pad);
    const boxRight = Math.min(viewportWidth - margin, rect.right + pad);
    const boxHeight = Math.max(0, boxBottom - boxTop);
    const boxWidth = Math.max(0, boxRight - boxLeft);

    spotlight.style.top = `${boxTop}px`;
    spotlight.style.left = `${boxLeft}px`;
    spotlight.style.width = `${boxWidth}px`;
    spotlight.style.height = `${boxHeight}px`;

    const calloutWidth = Math.min(280, viewportWidth - 40);
    const left = Math.max(16, Math.min(boxLeft, viewportWidth - calloutWidth - 16));

    // 說明卡放在框的下面；下面空間不夠（框已經很靠近畫面底部）就改放上面。
    // 一律用夾好的 boxTop／boxBottom 來算，不用原始 rect，才不會被爆出畫面的座標帶歪。
    const spaceBelow = viewportHeight - boxBottom;
    const calloutOnTop = spaceBelow < 160;

    callout.style.left = `${left}px`;
    if (calloutOnTop) {
      callout.style.top = 'auto';
      callout.style.bottom = `${viewportHeight - boxTop + 16}px`;
    } else {
      callout.style.bottom = 'auto';
      callout.style.top = `${boxBottom + 16}px`;
    }
  }

  function renderDots() {
    dotsEl.innerHTML = steps
      .map((_, i) => `<span class="tour-dot${i === index ? ' tour-dot--active' : ''}"></span>`)
      .join('');
  }

  function showStep(i) {
    index = i;
    const el = steps[index];
    textEl.textContent = el.dataset.tourText || '';
    nextBtn.textContent = index === steps.length - 1 ? '知道了' : '下一步';
    renderDots();

    // 目標比畫面矮就置中；比畫面高（例如很長的表單）就對齊到頂端，
    // 讓可見的那一段從有意義的開頭（標題）開始，而不是卡在中段。
    const viewportHeight = document.documentElement.clientHeight;
    const tall = el.getBoundingClientRect().height > viewportHeight - 160;
    el.scrollIntoView({ block: tall ? 'start' : 'center', behavior: 'smooth' });
    waitForScrollSettle(() => positionOn(el));
  }

  function start() {
    overlay.hidden = false;
    document.body.classList.add('tour-active');
    showStep(0);
  }

  function close(remember) {
    overlay.hidden = true;
    document.body.classList.remove('tour-active');
    if (remember) {
      try {
        localStorage.setItem(storageKey, '1');
      } catch (e) {
        // 存不進去（例如無痕模式）也沒關係，頂多下次再跳出來一次。
      }
    }
  }

  nextBtn.addEventListener('click', () => {
    if (index < steps.length - 1) {
      showStep(index + 1);
    } else {
      close(true);
    }
  });
  skipBtn.addEventListener('click', () => close(true));
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) close(true);
  });
  window.addEventListener('resize', () => {
    if (!overlay.hidden) positionOn(steps[index]);
  });

  tourBtn.addEventListener('click', start);

  let seen = false;
  try {
    seen = localStorage.getItem(storageKey) === '1';
  } catch (e) {
    seen = false;
  }
  if (!seen) {
    setTimeout(start, 500);
  }
});
