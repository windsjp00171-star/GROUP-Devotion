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

  verses.forEach((verse) => {
    verse.addEventListener('click', () => {
      verses.forEach((v) => v.classList.remove('verse--marked'));
      verse.classList.add('verse--marked');
      input.value = verse.dataset.verseIndex;
    });
  });
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
