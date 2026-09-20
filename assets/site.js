(function () {
  var btn = document.querySelector('.menu-btn'), nav = document.getElementById('nav');
  if (btn && nav) {
    btn.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    nav.addEventListener('click', function (e) { if (e.target.tagName === 'A') nav.classList.remove('open'); });
  }
  // Click-to-load YouTube player (privacy-enhanced domain, nothing loads until the click).
  var p = document.querySelector('.player');
  if (p) {
    var b = p.querySelector('.player-btn');
    if (b) b.addEventListener('click', function () {
      var f = document.createElement('iframe');
      f.src = 'https://www.youtube-nocookie.com/embed/' + p.dataset.id + '?autoplay=1&rel=0&modestbranding=1';
      f.title = 'YouTube video player';
      f.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
      f.allowFullscreen = true;
      f.referrerPolicy = 'strict-origin-when-cross-origin';
      p.replaceChildren(f);
    });
  }
  // Archive filters
  var chips = document.querySelectorAll('.fchip');
  if (chips.length) {
    var cards = document.querySelectorAll('#all .card');
    var apply = function (k) {
      chips.forEach(function (c) { c.classList.toggle('on', c.dataset.k === k); });
      cards.forEach(function (c) { c.hidden = !(k === 'all' || c.dataset.kind === k); });
    };
    chips.forEach(function (c) { c.addEventListener('click', function () { apply(c.dataset.k); }); });
    var q = new URLSearchParams(location.search).get('k');
    if (q) apply(q);
  }
})();
