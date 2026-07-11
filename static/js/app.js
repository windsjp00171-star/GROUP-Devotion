// 純 JS，只處理畫面上的小互動，不是前端框架。

document.addEventListener('DOMContentLoaded', () => {
  initTourPopover();
  initVerseMarking();
});

function initTourPopover() {
  const btn = document.querySelector('[data-tour]');
  const popover = document.getElementById('tour-popover');
  const text = document.getElementById('tour-popover-text');
  const closeBtn = document.getElementById('tour-popover-close');
  if (!btn || !popover || !text || !closeBtn) return;

  const copy = {
    home: '每天這裡會出現同一段經文。點一句摸到你的、或寫下一點點，都可以——不寫也沒關係。',
    collision: '這些小花小果，是小組裡每個人在同一段經文停下的地方。點點看，你會看見他們停在哪裡、想到了什麼。',
  };

  const target = document.querySelector('[data-tour-target]');
  const key = target ? target.dataset.tourTarget : 'home';
  text.textContent = copy[key] || copy.home;

  btn.addEventListener('click', () => {
    popover.hidden = !popover.hidden;
  });
  closeBtn.addEventListener('click', () => {
    popover.hidden = true;
  });
}

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
