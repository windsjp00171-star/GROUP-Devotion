// 純 JS，只處理畫面上的小互動，不是前端框架。
// 導覽（右上角「？」、聚焦式導覽）在 tour.js 裡，不是這裡。

document.addEventListener('DOMContentLoaded', () => {
  initVerseMarking();
  initSubmitFeedback();
});

function initVerseMarking() {
  const verses = document.querySelectorAll('.verse');
  const input = document.getElementById('verse-index-input');
  if (!verses.length || !input) return;

  const hint = document.getElementById('selected-verse');
  const hintText = document.getElementById('selected-verse-text');
  const clearBtn = document.getElementById('selected-verse-clear');

  function clearMark() {
    verses.forEach((v) => v.classList.remove('verse--marked'));
    input.value = '';
    if (hint) hint.hidden = true;
  }

  verses.forEach((verse) => {
    verse.addEventListener('click', () => {
      const alreadyMarked = verse.classList.contains('verse--marked');
      clearMark();
      if (alreadyMarked) return; // 再點一次同一句：取消標記，回到「沒有針對哪一句」

      verse.classList.add('verse--marked');
      input.value = verse.dataset.verseIndex;
      if (hint && hintText) {
        hintText.textContent = verse.textContent.trim();
        hint.hidden = false;
      }
      // 手機上點擊回饋容易被忽略，有支援的話震一下加強「有點到」的感覺。
      if (navigator.vibrate) navigator.vibrate(12);
    });
  });

  if (clearBtn) {
    clearBtn.addEventListener('click', clearMark);
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
