function showTab(id) {
  document.querySelectorAll('.tab-content').forEach(function(t) { t.classList.remove('active'); });
  document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
  document.getElementById(id).classList.add('active');
  event.target.classList.add('active');
  window.scrollTo(0, 0);
}
