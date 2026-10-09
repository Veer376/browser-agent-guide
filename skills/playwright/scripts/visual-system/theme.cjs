// One source for cursor, pill, eyes and snooze. Keep colors monochrome in both
// themes; do not reintroduce the rejected external black border / drop shadow.
const themes = Object.freeze({
  light: Object.freeze({black: '#151515', white: '#ffffff'}),
  dark: Object.freeze({black: '#0a0a0a', white: '#f7f7f7'}),
});

function normalizeTheme(theme) {
  return ['light', 'dark'].includes(theme) ? theme : 'auto';
}

function themeCSS() {
  return `
x-pw-action-cursor{--pw-ink-black:${themes.light.black};--pw-ink-white:${themes.light.white}}
@media(prefers-color-scheme: dark){x-pw-action-cursor:not([data-pw-theme="light"]){--pw-ink-black:${themes.dark.black};--pw-ink-white:${themes.dark.white}}}
x-pw-action-cursor[data-pw-theme="dark"]{--pw-ink-black:${themes.dark.black};--pw-ink-white:${themes.dark.white}}
x-pw-action-cursor[data-pw-theme="light"]{--pw-ink-black:${themes.light.black};--pw-ink-white:${themes.light.white}}
`;
}

module.exports = {themes, normalizeTheme, themeCSS};
