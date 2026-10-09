const {themeCSS} = require('./theme.cjs');

const CSS = `
/* Host dimensions match the exact original cursor. The pill is a separate DOM
   element attached to that host, with ONLY a white border (no dark rim). */
x-pw-action-cursor{width:46px!important;height:48px!important;transform:translate(-6px,-5px);filter:none!important}
x-pw-action-cursor>svg{width:46px!important;height:48px!important;overflow:visible}
${themeCSS()}
.pw-agent-pill{position:absolute;left:34px;top:31px;width:58px;height:27px;box-sizing:border-box;
 background:var(--pw-ink-black);border:2px solid var(--pw-ink-white);border-radius:999px;
 box-shadow:none!important;display:flex;align-items:center;justify-content:center;pointer-events:none;
 transform-origin:18% 46%;isolation:isolate}
.pw-agent-eyes{display:flex;gap:11px;align-items:center;justify-content:center}
.pw-agent-eyes{transition:transform 150ms ease-out}
.pw-agent-z{pointer-events:none}
x-pw-action-cursor[data-pw-agent-state="glance-left"] .pw-agent-eyes{transform:translateX(-3px)}
x-pw-action-cursor[data-pw-agent-state="glance-right"] .pw-agent-eyes{transform:translateX(3px)}
x-pw-action-cursor[data-pw-agent-state="glance-up"] .pw-agent-eyes{transform:translateY(-3px)}
x-pw-action-cursor[data-pw-agent-state="glance-down"] .pw-agent-eyes{transform:translateY(3px)}
.pw-agent-eye{width:6px;height:6px;display:block;background:var(--pw-ink-white);border-radius:50%;
 transform-origin:center;flex:none}
.pw-agent-z{position:absolute;top:-11px;left:52px;color:var(--pw-ink-black);font:700 13px/1 ui-monospace,monospace;
 -webkit-text-stroke:.6px var(--pw-ink-white);text-shadow:none;opacity:0}
.pw-agent-z-2{top:-5px;left:48px;font-size:10px}
x-pw-action-cursor[data-pw-agent-state="idle"] .pw-agent-eye{animation:pw-agent-blink 6.2s ease-in-out infinite}
x-pw-action-cursor[data-pw-agent-state="idle"] .pw-agent-eye:last-child{animation-delay:40ms}
x-pw-action-cursor[data-pw-agent-state="blink"] .pw-agent-eye{animation:pw-agent-blink-once 650ms both}
x-pw-action-cursor[data-pw-agent-state="typing"] .pw-agent-eye:first-child{animation:pw-agent-typing .55s ease-in-out infinite}
x-pw-action-cursor[data-pw-agent-state="typing"] .pw-agent-eye:last-child{animation:pw-agent-typing .55s ease-in-out .16s infinite}
x-pw-action-cursor[data-pw-agent-state="scroll-down"] .pw-agent-eyes{animation:pw-look-down 1.8s ease-in-out both}
x-pw-action-cursor[data-pw-agent-state="scroll-up"] .pw-agent-eyes{animation:pw-look-up 1.8s ease-in-out both}
x-pw-action-cursor[data-pw-agent-state="scroll-left"] .pw-agent-eyes{animation:pw-look-left 1.8s ease-in-out both}
x-pw-action-cursor[data-pw-agent-state="scroll-right"] .pw-agent-eyes{animation:pw-look-right 1.8s ease-in-out both}
x-pw-action-cursor[data-pw-agent-state="reading"] .pw-agent-eyes{animation:pw-agent-read 1.85s ease-in-out infinite}
x-pw-action-cursor[data-pw-agent-state="inspecting"] .pw-agent-eyes{animation:pw-agent-read 2.1s ease-in-out infinite}
x-pw-action-cursor[data-pw-agent-state="capture"] .pw-agent-eye{animation:pw-agent-blink-once .56s both}
x-pw-action-cursor[data-pw-agent-state="heavy"] .pw-agent-pill{animation:pw-nod 1.3s ease-in-out both}
x-pw-action-cursor[data-pw-agent-state="nod"] .pw-agent-pill{animation:pw-deep-nod 1.6s ease-in-out both}
x-pw-action-cursor[data-pw-agent-state="heavy"] .pw-agent-eye,
x-pw-action-cursor[data-pw-agent-state="nod"] .pw-agent-eye{animation:pw-heavy-eyes 1.5s ease-in-out both}
x-pw-action-cursor[data-pw-agent-state="jolt"] .pw-agent-pill{animation:pw-jolt .68s cubic-bezier(.2,.9,.2,1) both}
x-pw-action-cursor[data-pw-agent-state="jolt"] .pw-agent-eye{animation:pw-snap-eye .68s both}
x-pw-action-cursor[data-pw-agent-state="exhausted"] .pw-agent-eye{transform:scaleY(.45)}
x-pw-action-cursor[data-pw-agent-state="falling"] .pw-agent-pill{animation:pw-finally-sleep 1.9s both}
x-pw-action-cursor[data-pw-agent-state="falling"] .pw-agent-eye{animation:pw-heavy-eyes 1.9s both}
x-pw-action-cursor[data-pw-agent-state="sleep"] .pw-agent-pill{animation:pw-sleep-breath 3.8s ease-in-out infinite}
x-pw-action-cursor[data-pw-agent-state="sleep"] .pw-agent-eye{transform:scaleY(.12)}
x-pw-action-cursor[data-pw-agent-state="sleep"] .pw-agent-z{animation:pw-floating-z 2.8s ease-out infinite}
x-pw-action-cursor[data-pw-agent-state="sleep"] .pw-agent-z-2{animation-delay:-1.35s}
x-pw-action-cursor[data-pw-agent-state="wake"] .pw-agent-pill{animation:pw-wake .76s cubic-bezier(.2,1,.25,1) both}
x-pw-action-cursor[data-pw-agent-state="wake"] .pw-agent-eye{animation:pw-snap-eye .76s both}
@keyframes pw-agent-blink{0%,24%,27%,49%,52%,100%{transform:scaleY(1)}25.5%,50.5%{transform:scaleY(.12)}}
@keyframes pw-agent-blink-once{0%,17%,31%,67%,100%{transform:scaleY(1)}23%,25%{transform:scaleY(.1)}72%,77%{transform:scaleY(.12)}}
@keyframes pw-agent-typing{0%,100%{transform:translateY(0)}38%{transform:translateY(-1.7px)}70%{transform:translateY(1px)}}
@keyframes pw-look-down{0%{transform:translate(0,0)}16%,57%{transform:translateY(5.5px)}85%,100%{transform:translate(0,0)}}
@keyframes pw-look-up{0%{transform:translate(0,0)}16%,57%{transform:translateY(-5.5px)}85%,100%{transform:translate(0,0)}}
@keyframes pw-look-left{0%{transform:translate(0,0)}16%,57%{transform:translateX(-6px)}85%,100%{transform:translate(0,0)}}
@keyframes pw-look-right{0%{transform:translate(0,0)}16%,57%{transform:translateX(6px)}85%,100%{transform:translate(0,0)}}
@keyframes pw-agent-read{0%,12%,100%{transform:translateX(-3px)}48%,64%{transform:translateX(3px)}}
@keyframes pw-heavy-eyes{0%,12%{transform:scaleY(1)}36%{transform:scaleY(.55)}53%{transform:scaleY(.7)}84%,100%{transform:scaleY(.11)}}
@keyframes pw-nod{0%{transform:rotate(0)}55%{transform:rotate(6deg) translateY(3px)}100%{transform:rotate(11deg) translateY(6px)}}
@keyframes pw-deep-nod{0%{transform:rotate(1deg)}70%{transform:rotate(12deg) translateY(7px)}100%{transform:rotate(17deg) translateY(10px)}}
@keyframes pw-jolt{0%{transform:rotate(14deg) translateY(8px)}17%{transform:rotate(-9deg) translateY(-5px)}38%{transform:rotate(4deg) translateY(1px)}60%{transform:rotate(-2.5deg)}100%{transform:rotate(0)}}
@keyframes pw-snap-eye{0%{transform:scaleY(.1)}19%,55%{transform:scaleY(1.4)}100%{transform:scaleY(1)}}
@keyframes pw-finally-sleep{0%{transform:rotate(1deg)}55%{transform:rotate(5.5deg) translateY(3px)}100%{transform:rotate(8deg) translateY(3px)}}
@keyframes pw-sleep-breath{0%,100%{transform:rotate(8deg) translateY(3px)}50%{transform:rotate(9deg) translateY(4px)}}
@keyframes pw-floating-z{0%{opacity:0;transform:translate(0,5px) scale(.65)}16%{opacity:.9}49%{opacity:.95}75%{opacity:.1}100%{opacity:0;transform:translate(8px,-17px) scale(1.05)}}
@keyframes pw-wake{0%{transform:rotate(9deg) translateY(4px)}15%{transform:rotate(-9deg) translateY(-5px)}37%{transform:rotate(4deg) translateY(1px)}66%{transform:rotate(-2deg)}100%{transform:rotate(0)}}
@media(prefers-reduced-motion:reduce){.pw-agent-pill,.pw-agent-eye,.pw-agent-eyes,.pw-agent-z{animation:none!important;transition:none!important}}
`;

module.exports = {CSS};
