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

  function positionOn(el) {
    const rect = el.getBoundingClientRect();
    const pad = 8;
    spotlight.style.top = `${rect.top - pad + window.scrollY}px`;
    spotlight.style.left = `${rect.left - pad + window.scrollX}px`;
    spotlight.style.width = `${rect.width + pad * 2}px`;
    spotlight.style.height = `${rect.height + pad * 2}px`;

    const viewportWidth = document.documentElement.clientWidth;
    const calloutWidth = Math.min(280, viewportWidth - 40);
    let left = rect.left + window.scrollX;
    left = Math.max(16, Math.min(left, viewportWidth - calloutWidth - 16));

    callout.style.top = `${rect.bottom + window.scrollY + 16}px`;
    callout.style.left = `${left}px`;
  }

  function renderDots() {
    dotsEl.innerHTML = steps
      .map((_, i) => `<span class="tour-dot${i === index ? ' tour-dot--active' : ''}"></span>`)
      .join('');
  }

  function showStep(i) {
    index = i;
    const el = steps[index];
    el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    textEl.textContent = el.dataset.tourText || '';
    nextBtn.textContent = index === steps.length - 1 ? '知道了' : '下一步';
    renderDots();
    // 等捲動穩定再量位置，不然抓到的是捲動前的座標。
    requestAnimationFrame(() => requestAnimationFrame(() => positionOn(el)));
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
