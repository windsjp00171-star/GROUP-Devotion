// 純 JS，只處理畫面上的小互動，不是前端框架。
// 導覽（右上角「？」、聚焦式導覽）在 tour.js 裡，不是這裡。

document.addEventListener('DOMContentLoaded', () => {
  initVerseMarking();
  initSubmitFeedback();
  initSortSelect();
  initReactions();
});

function initReactions() {
  // 反應改成不整頁重整：攔截送出、用 fetch 打 API、就地更新那一則的反應區。
  // 沒有 JS（或離線 fetch 失敗）就退回一般表單送出，功能不會消失。
  const kindsEl = document.getElementById('reaction-kinds');
  if (!kindsEl) return;
  let KINDS;
  try {
    KINDS = JSON.parse(kindsEl.textContent);
  } catch (e) {
    return;
  }

  document.querySelectorAll('[data-react-form]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const item = form.closest('.feed-item');
      fetch(form.action, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        body: new FormData(form),
      })
        .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
        .then((data) => applyReactionUpdate(item, data, KINDS))
        .catch(() => form.submit()); // 出錯（例如離線）就退回一般送出
    });
  });
}

function applyReactionUpdate(item, data, KINDS) {
  if (!item) return;
  const mine = data.my_reaction_kind;

  // 每個反應按鈕：對到我目前選的那種就 active，下一次點它是取消（kind 送空字串）。
  item.querySelectorAll('[data-react-form]').forEach((form) => {
    const btn = form.querySelector('.feed-item__react-btn');
    const kindInput = form.querySelector('input[name="kind"]');
    if (!btn) return;
    const active = btn.dataset.kind === mine;
    btn.classList.toggle('feed-item__react-btn--active', active);
    if (kindInput) kindInput.value = active ? '' : btn.dataset.kind;
  });

  // 重建反應文字列（用 textContent，名字是使用者輸入的暱稱，不能用 innerHTML）。
  const list = item.querySelector('[data-reactions-list]');
  if (list) {
    list.textContent = '';
    (data.reactions || []).forEach((r) => {
      const info = KINDS[r.kind];
      if (!info) return;
      const p = document.createElement('p');
      p.className = 'feed-item__reaction-line';
      p.textContent = `${info.emoji} ${r.mine ? '你' : r.name}${info.phrase}`;
      list.appendChild(p);
    });
  }
  if (navigator.vibrate) navigator.vibrate(8);
}

function initSortSelect() {
  // 排序下拉選單：選了就直接跳到那個排序的網址（option 的 value 就是目標網址）。
  document.querySelectorAll('[data-sort-nav]').forEach((select) => {
    select.addEventListener('change', () => {
      if (select.value) window.location.href = select.value;
    });
  });
}

function initVerseMarking() {
  // 每一句的標記是各自獨立切換的，不是「點新的一句就取消舊的」——
  // 可以同時針對好幾句經文留一則領受，點已經標記的那句就是取消那一句。
  const verses = document.querySelectorAll('.verse');
  const input = document.getElementById('verse-index-input');
  if (!verses.length || !input) return;

  const hint = document.getElementById('selected-verse');
  const hintText = document.getElementById('selected-verse-text');
  const clearBtn = document.getElementById('selected-verse-clear');

  function syncSelection() {
    const marked = Array.from(verses).filter((v) => v.classList.contains('verse--marked'));
    input.value = marked.map((v) => v.dataset.verseIndex).join(',');
    if (!hint || !hintText) return;
    if (!marked.length) {
      hint.hidden = true;
      return;
    }
    // 只取經文本身（.verse-text），不要把前面的節號也塞進提示裡。
    hintText.textContent = marked
      .map((v) => (v.querySelector('.verse-text') || v).textContent.trim())
      .join('／');
    hint.hidden = false;
  }

  verses.forEach((verse) => {
    verse.addEventListener('click', () => {
      verse.classList.toggle('verse--marked');
      // 手機上點擊回饋容易被忽略，有支援的話震一下加強「有點到」的感覺（取消標記不用震）。
      if (verse.classList.contains('verse--marked') && navigator.vibrate) navigator.vibrate(12);
      syncSelection();
    });
  });

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      verses.forEach((v) => v.classList.remove('verse--marked'));
      syncSelection();
    });
  }
}

function initSubmitFeedback() {
  // 表單送出後是一般的 POST + 轉頁，連線稍慢時畫面會有一段空白。
  // 按鈕先鎖住、換成「處理中…」，避免使用者以為沒反應而重複點擊。
  document.querySelectorAll('form').forEach((form) => {
    form.addEventListener('submit', () => {
      const btn = form.querySelector('button[type="submit"]');
      if (!btn) return;
      btn.textContent = '處理中…';
      btn.disabled = true;
    });
  });
}
