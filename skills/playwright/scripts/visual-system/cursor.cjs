// The original 46x48 PNG is preserved in ../assets for compatibility.
// This vector silhouette has a single WHITE outline: no external dark rim.
// Keep the SVG self-contained so it can be injected into a closed shadow root.
const WIDTH = 46;
const HEIGHT = 48;
const silhouette = Object.freeze({
  outer: 'M 9 6 C 7 5.8 5.7 8.3 6.5 11.6 L 14.1 35.8 C 15.4 40.6 18 43.3 21.5 41.9 C 25.2 40.8 26.2 36.1 28.5 29.5 L 38.9 25.8 C 43.3 24.1 43.8 19.4 40.5 17.7 L 15 7.4 C 12.7 6.5 10.5 5.7 9 6 Z',
  inner: 'M 10.2 9.7 C 9.4 9.6 8.9 11.9 9.8 14.9 L 17.6 35.8 C 19.1 40.1 21.9 40 23.2 35.2 L 26.3 26.4 L 37 22.7 C 39.5 21.8 40.1 20.1 37.2 19 L 13.4 10.3 C 12.1 9.9 11.2 9.7 10.2 9.7 Z',
});

function cursorMarkup() {
  return `<path d="${silhouette.outer}" fill="var(--pw-ink-white,white)"/><path d="${silhouette.inner}" fill="var(--pw-ink-black,#111)"/>`;
}

module.exports = {WIDTH, HEIGHT, silhouette, cursorMarkup};
