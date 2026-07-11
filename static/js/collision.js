// 碰撞畫面：點一個花／果／蝶／石記號，打開底部的領受卡。
// 內容已經由伺服器端 Jinja2 渲染進 data-* 屬性，這裡不另外打 API。

document.addEventListener('DOMContentLoaded', () => {
  const marks = document.querySelectorAll('.garden-bed .mark');
  const card = document.getElementById('reveal-card');
  if (!marks.length || !card) return;

  const nameEl = document.getElementById('reveal-name');
  const avatarEl = document.getElementById('reveal-avatar');
  const verseEl = document.getElementById('reveal-verse');
  const noteEl = document.getElementById('reveal-note');
  const closeBtn = document.getElementById('reveal-close');

  let activeMark = null;

  function openCard(mark) {
    activeMark = mark;
    nameEl.textContent = mark.dataset.name;
    avatarEl.textContent = mark.dataset.initial;
    verseEl.textContent = `「${mark.dataset.verse}」`;

    const note = mark.dataset.note || '';
    if (note.trim().length > 0) {
      noteEl.textContent = note;
      noteEl.classList.remove('reveal-card__note--empty');
    } else {
      noteEl.textContent = `${mark.dataset.name} 也在這句停下了腳步，沒有多寫什麼`;
      noteEl.classList.add('reveal-card__note--empty');
    }
    card.hidden = false;
  }

  function closeCard() {
    activeMark = null;
    card.hidden = true;
  }

  marks.forEach((mark) => {
    mark.addEventListener('click', () => {
      if (activeMark === mark) {
        closeCard();
      } else {
        openCard(mark);
      }
    });
  });

  closeBtn.addEventListener('click', closeCard);
});
