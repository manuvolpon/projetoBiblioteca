function toggleMenu() {
  const nav = document.querySelector('.nav');
  if (!nav) return;
  nav.classList.toggle('nav-open');
}
