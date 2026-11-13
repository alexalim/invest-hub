// 음원 파일 없이 Web Audio 로 그 자리에서 만드는 소리 (목탁, 종, 멜로디)
let ctx = null
function ac() {
  try { ctx = ctx || new (window.AudioContext || window.webkitAudioContext)(); if (ctx.state === 'suspended') ctx.resume(); return ctx } catch { return null }
}
function tone(c, freq, dur, vol, type = 'sine', at = 0) {
  const o = c.createOscillator(); const g = c.createGain(); const t = c.currentTime + at
  o.type = type; o.frequency.value = freq
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.006); g.gain.exponentialRampToValueAtTime(0.0001, t + dur)
  o.connect(g).connect(c.destination); o.start(t); o.stop(t + dur + 0.05)
  return o
}

export function knock(at = 0) { const c = ac(); if (!c) return; tone(c, 610, 0.1, 0.5, 'triangle', at); tone(c, 915, 0.05, 0.22, 'sine', at); tone(c, 305, 0.07, 0.2, 'sine', at) }
export function stamp() { const c = ac(); if (!c) return; tone(c, 150, 0.12, 0.5, 'sine'); tone(c, 90, 0.16, 0.35, 'triangle') }
export function bell() {
  const c = ac(); if (!c) return
  ;[[392, 0.3, 3.4], [786, 0.16, 2.8], [1180, 0.1, 2.2], [1574, 0.06, 1.6], [2110, 0.03, 1.1]].forEach(([f, v, d]) => tone(c, f, d, v))
}

const SEMI = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }
function freq(n) { const m = /^([A-G])(#?)(\d)$/.exec(n); return 440 * 2 ** ((SEMI[m[1]] + (m[2] ? 1 : 0) + (+m[3] - 4) * 12 - 9) / 12) }

// notes: [['G4', 박자수], ...]. 끝나면 처음부터 다시 연주한다. 멈추는 함수를 돌려준다.
export function playMelody(notes, beat = 0.5) {
  const c = ac(); if (!c) return () => {}
  let live = []; let timer = null; let stopped = false
  const round = () => {
    if (stopped) return
    let at = 0.05
    live = notes.map(([n, len]) => { const d = len * beat; const o = n ? [tone(c, freq(n), d * 1.6, 0.16, 'sine', at), tone(c, freq(n) * 2, d * 1.1, 0.05, 'sine', at)] : []; at += d; return o }).flat()
    timer = setTimeout(round, (at + beat * 2) * 1000)
  }
  round()
  return () => { stopped = true; clearTimeout(timer); live.forEach(o => { try { o.stop() } catch { /* 이미 끝난 음 */ } }) }
}
