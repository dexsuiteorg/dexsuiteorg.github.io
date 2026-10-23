// Page behaviour: the task carousel (bulma-carousel) and nothing else.
document.addEventListener('DOMContentLoaded', function () {
  if (window.bulmaCarousel) {
    bulmaCarousel.attach('.carousel', {
      slidesToScroll: 1,
      slidesToShow: window.innerWidth < 769 ? 1 : 3,
      loop: true,
      infinite: true,
      autoplay: true,
      autoplaySpeed: 5000,
      pauseOnHover: true,
    });
  }
  // cloned slides from the infinite carousel do not autoplay on their own
  document.querySelectorAll('.results-carousel video').forEach(function (v) {
    v.muted = true;
    var p = v.play();
    if (p && p.catch) p.catch(function () {});
  });
});
