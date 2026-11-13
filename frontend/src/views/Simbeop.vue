<template>
  <!-- 심법: 매매 전에 마음을 가라앉히는 곳. 격언 / 목탁 / 종이 part 로 갈리고, 기록·구절 카드·지난 기록은 셋이 같이 쓴다.
       넓은 화면은 두 칸(왼쪽 누르는 곳, 오른쪽 기록), 좁은 화면은 한 줄이며 순서는 CSS order 로 바꾼다. -->
  <div class="sb" :style="{ '--sb': c.color }">
    <div class="head"><h1>{{ c.title }}</h1><div class="muted small">{{ c.sub }}</div></div>

    <div class="main">
      <div v-if="cats" class="cats">
        <button v-for="k in cats" :key="k[0]" :class="{ on: cat === k[0] }" @click="cat = k[0]">{{ k[0] }} <span class="tiny">{{ k[1] }}</span></button>
      </div>

      <div class="stage">
        <span v-if="breath" class="halo" />
        <button class="inst" :class="[part, { hit: pulse }]" :aria-label="c.act" @click="hit">
          <svg v-if="part === 'sayings'" viewBox="0 0 120 120" aria-hidden="true">
            <circle cx="60" cy="60" r="54" fill="var(--sb)" /><circle cx="60" cy="60" r="45" fill="none" stroke="#fff" stroke-width="2.5" opacity=".9" />
            <text x="60" y="56" text-anchor="middle" font-size="26" font-weight="800" fill="#fff">다</text><text x="60" y="86" text-anchor="middle" font-size="26" font-weight="800" fill="#fff">짐</text></svg>
          <svg v-else-if="part === 'moktak'" viewBox="0 0 260 260" aria-hidden="true">
            <circle v-for="i in 108" :key="i" :cx="130 + 122 * Math.sin((i - 1) / 108 * 2 * Math.PI)" :cy="130 - 122 * Math.cos((i - 1) / 108 * 2 * Math.PI)" :r="i <= bead ? 3.4 : 2.6" :fill="i <= bead ? 'var(--sb-ink)' : 'var(--line)'" />
            <ellipse cx="124" cy="212" rx="58" ry="7" fill="#000" opacity=".12" />
            <path d="M112 84 q12 -16 24 0" stroke="#5c3a1a" stroke-width="6" fill="none" stroke-linecap="round" />
            <ellipse cx="124" cy="146" rx="70" ry="62" fill="#a8703a" /><ellipse cx="124" cy="138" rx="70" ry="58" fill="#c58a4c" />
            <ellipse cx="100" cy="112" rx="26" ry="14" fill="#fff" opacity=".13" />
            <path d="M74 158 Q124 182 174 158" stroke="#5c3a1a" stroke-width="8" fill="none" stroke-linecap="round" />
            <circle cx="72" cy="157" r="6" fill="#5c3a1a" /><circle cx="176" cy="157" r="6" fill="#5c3a1a" />
            <g class="mallet"><line x1="236" y1="44" x2="202" y2="110" stroke="#7a4a22" stroke-width="5" stroke-linecap="round" /><circle cx="200" cy="114" r="10" fill="#b5773c" /></g></svg>
          <svg v-else viewBox="0 0 160 190" aria-hidden="true">
            <circle cx="80" cy="14" r="9" fill="none" stroke="#8a6a1f" stroke-width="5" />
            <path d="M80 22 C40 22 38 86 22 150 L138 150 C122 86 120 22 80 22 Z" fill="#d4a93a" /><path d="M68 34 C52 60 48 110 44 146 L58 146 C60 104 62 60 72 34 Z" fill="#fff" opacity=".22" />
            <rect x="10" y="148" width="140" height="11" rx="5" fill="#b48a26" /><circle class="clap" cx="80" cy="172" r="10" fill="#8a6a1f" /></svg>
        </button>
        <span v-for="f in floats" :key="f" class="plus">+1</span>
      </div>
      <div v-if="part === 'moktak'" class="small muted center">
        <template v-if="breath"><b>{{ breathIn ? '들이쉬고' : '내쉬고' }}</b> · </template>염주 {{ bead }} / 108 · 한 바퀴 {{ Math.floor(p.today.value / 108) }}번</div>

      <div class="card verse" aria-live="polite">
        <span v-if="part === 'sayings' && p.today.value" :key="p.today.value" class="seal" aria-hidden="true">다짐</span>
        <div :key="cur.t" class="fade">
          <div class="v-t" :class="{ han: part === 'moktak' }">{{ cur.t }}</div>
          <div v-if="cur.s" class="muted v-s">{{ cur.s }}</div>
          <div class="v-f"><span class="tiny muted">{{ cur.cat || '' }}</span><span class="tiny src">{{ cur.src }}</span></div>
        </div>
      </div>

      <div class="acts">
        <button :class="{ on: p.isFav(cur.t) }" @click="p.toggleFav(cur.t)">{{ p.isFav(cur.t) ? '♥ 담음' : '♡ 담기' }}</button>
        <button :class="{ on: hold }" :title="`켜 두면 ${c.act}도 구절이 바뀌지 않습니다`" @click="hold = !hold">이 구절에 머물기</button>
        <button @click="copy(text(cur), '구절을 복사했습니다')">구절 복사</button>
        <button @click="saveImage">이미지로 저장</button>
        <button v-if="part === 'bell' && canSpeak" :class="{ on: speaking }" @click="speak">소리 내어 읽기</button>
      </div>
      <div class="acts">
        <template v-if="c.speeds">
          <button :class="{ on: auto }" :title="'오늘 목표를 채우면 멈춥니다'" @click="auto = !auto">{{ c.autoLabel }}</button>
          <button @click="speed = (speed + 1) % c.speeds.length">{{ c.speedWord }}: {{ c.speeds[speed][0] }}</button>
        </template>
        <button v-if="part === 'moktak'" :class="{ on: breath }" title="4초 들이쉬고 6초 내쉽니다" @click="breath = !breath">숨 고르기</button>
        <button :class="{ on: p.rec.value.sound }" @click="p.rec.value.sound = !p.rec.value.sound">소리 {{ p.rec.value.sound ? '켜짐' : '꺼짐' }}</button>
      </div>
      <div class="tiny faint center hint">{{ c.hint }}</div>
    </div>

    <div class="side">
      <div class="daily">
        <div class="tiny lab">오늘의 {{ c.word }} · {{ dateLabel }}</div>
        <div class="d-t" :class="{ han: part === 'moktak' }">{{ daily.t }}</div>
        <div v-if="daily.s" class="small">{{ daily.s }}</div>
        <div class="tiny faint">{{ daily.src }}</div>
      </div>

      <div class="stats">
        <div><b>{{ p.total.value.toLocaleString('ko-KR') }}</b><span>{{ c.totalLabel }}</span></div>
        <div><b :key="p.today.value" class="bump">{{ p.today.value.toLocaleString('ko-KR') }}</b><span>오늘</span></div>
        <div><b>{{ p.stats.value.streak }}일</b><span>연속</span></div>
      </div>
      <div class="goalbox">
        <div class="goal">
          <div class="small">오늘 목표 <b>{{ p.today.value.toLocaleString('ko-KR') }} / {{ goal.toLocaleString('ko-KR') }}</b><span v-if="p.today.value >= goal" class="chip green" style="margin-left:6px">달성</span></div>
          <div class="goals"><button v-for="g in c.goals" :key="g" class="ghost" :class="{ on: goal === g }" @click="p.rec.value.goal = g">{{ g.toLocaleString('ko-KR') }}</button></div>
        </div>
        <div class="bar-bg"><div class="bar-fg" :style="{ width: Math.min(100, (p.today.value / goal) * 100) + '%' }" /></div>
      </div>

      <div v-if="part === 'moktak'" class="sec center">
        <h3>명상 타이머</h3>
        <div class="acts"><button v-for="m in [5, 10, 20]" :key="m" :class="{ on: mins === m }" :disabled="remain !== null" @click="mins = m">{{ m }}분</button>
          <button class="primary" @click="toggleTimer">{{ remain === null ? '시작' : '멈춤' }}</button></div>
        <template v-if="remain !== null"><div class="clock">{{ Math.floor(remain / 60) }}:{{ String(remain % 60).padStart(2, '0') }}</div>
          <div class="bar-bg" style="width:100%"><div class="bar-fg" :style="{ width: (1 - remain / (mins * 60)) * 100 + '%' }" /></div></template>
        <div class="tiny faint">시간이 끝나면 목탁이 세 번 울립니다. 소리를 켜 두세요.</div>
      </div>

      <template v-if="part === 'bell'">
        <div class="sec center">
          <h3>찬송 멜로디</h3>
          <div class="acts"><button v-for="(m, i) in MELODIES" :key="m.name" :class="{ on: mel === i }" @click="pickMelody(i)">{{ m.name }}</button></div>
          <button class="primary" @click="toggleMelody">{{ stopMelody ? '■ 멈춤' : '▶ 멜로디 틀기' }}</button>
          <div class="tiny faint">종을 울리며 함께 들어 보세요. 끝나면 처음부터 다시 연주합니다.</div>
        </div>
        <details class="sec">
          <summary>말씀 찾기</summary>
          <input v-model="q" placeholder="낱말이나 책 이름 (예: 평안, 잠언)" style="width:100%;margin:8px 0">
          <div v-if="q.trim() && !found.length" class="small muted">찾는 말씀이 없습니다.</div>
          <button v-for="f in found" :key="f.src" class="row-b" @click="stay(f)">{{ f.t }}<span class="tiny src">{{ f.src }}</span></button>
          <div v-if="found.length" class="tiny faint" style="margin-top:6px">누르면 그 구절에 머뭅니다.</div>
        </details>
      </template>

      <details class="sec" :open="favs.length > 0">
        <summary>담아 둔 구절 <span class="small muted">{{ favs.length }}</span></summary>
        <div v-if="!favs.length" class="small muted" style="margin-top:8px">♡ 담기를 누르면 여기에 모입니다.</div>
        <div v-for="f in favs" :key="f.t" class="fav"><button class="row-b" @click="stay(f)">{{ f.t }}<span class="tiny src">{{ f.src }}</span></button>
          <button class="ghost" aria-label="빼기" @click="p.toggleFav(f.t)">✕</button></div>
      </details>

      <details class="sec" open>
        <summary>지난 기록</summary>
        <div class="small" style="margin:8px 0">함께한 날 {{ p.stats.value.days }}일 · 최장 연속 {{ p.stats.value.longest }}일 · 하루 최다 {{ p.stats.value.best.toLocaleString('ko-KR') }}번</div>
        <div class="heat"><template v-for="(w, i) in p.weeks.value" :key="i">
          <span v-for="d in w" :key="d.k" class="hc" :class="['l' + d.lv, { fut: d.future, now: d.today }]" :title="`${d.k} · ${d.n}번`" /></template></div>
        <div class="h-f tiny faint"><span>최근 12주, 오른쪽 끝이 이번 주</span><span class="lg">쉼 <i class="hc l0" /><i class="hc l1" /><i class="hc l2" /><i class="hc l3" /><i class="hc l4" /> 목표 달성</span></div>
        <div class="acts" style="justify-content:flex-start;margin-top:8px"><button @click="copy(p.summary(c.title, '번'), '기록을 복사했습니다')">기록 복사</button>
          <button @click="resetAsk">{{ asking ? '한 번 더 누르면 지워집니다' : '기록 초기화' }}</button></div>
        <div class="tiny faint" style="margin-top:6px">기록은 이 기기의 브라우저에 저장됩니다.</div>
      </details>

      <div class="foot tiny faint"><div v-for="n in c.notes" :key="n">{{ n }}</div></div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { toast } from '../lib/api'
import { ofTheDay, usePractice } from '../lib/practice'
import { MELODIES, MOKTAK, SAYINGS, VERSES } from '../lib/simbeopData'
import { bell, knock, playMelody, stamp } from '../lib/sound'

const props = defineProps({ part: { type: String, default: 'sayings' } })
const CFG = {
  sayings: { title: '투자 격언', sub: '매매 전에 도장을 한 번 찍고, 한 줄을 새기세요', word: '격언', list: SAYINGS, color: '#b3392f', totalLabel: '누적 다짐', goals: [1, 3, 5, 10], goal: 3,
    act: '도장을 찍어', play: stamp, hint: '도장을 누르거나 스페이스바를 누르세요',
    notes: ['시장에서 전해 오는 말은 「증시 격언」, 이 화면에서 새로 쓴 말은 「새로 쓴 다짐」으로 적었습니다. 풀이는 모두 새로 썼습니다.', '마음가짐을 위한 화면이며 특정 종목을 사거나 팔라는 뜻이 아닙니다.'] },
  moktak: { title: '마음 목탁', sub: '한 번 두드리고, 한 번 숨을 고르세요', word: '구절', list: MOKTAK, color: '#2f6b55', totalLabel: '누적 두드림', goals: [33, 108, 300, 1080], goal: 108,
    act: '목탁을 두드려', play: knock, hint: '목탁을 누르거나 스페이스바를 누르세요', autoLabel: '자동 두드림', speedWord: '속도', speeds: [['느리게', 2000], ['보통', 1200], ['빠르게', 700]],
    notes: ['한문 구절은 옛 경전과 고전의 원문이고, 우리말 풀이는 이 화면에서 새로 썼습니다.', '횟수는 마음을 모으기 위한 것일 뿐입니다. 숫자보다 한 번 한 번이 중요합니다.'] },
  bell: { title: '말씀 종', sub: '종을 울리면 말씀 한 구절이 찾아옵니다', word: '말씀', list: VERSES, color: '#b07a1a', totalLabel: '누적 울림', goals: [3, 7, 33, 108], goal: 7,
    act: '종을 울려', play: bell, hint: '종을 누르거나 스페이스바를 누르세요', autoLabel: '자동 울림', speedWord: '간격', speeds: [['3초', 3000], ['5초', 5000], ['10초', 10000]],
    notes: ['성경 본문은 저작권이 끝난 「성경전서 개역한글판」(1961)을 따랐습니다.', '멜로디는 저작권이 끝난 옛 곡조를 직접 연주한 것이며 가사는 넣지 않았습니다.'] },
}
const c = CFG[props.part] || CFG.sayings
const p = usePractice(props.part, c.goal)
const goal = computed(() => p.rec.value.goal || c.goal)
const daily = ofTheDay(c.list)
const now = new Date(); const dateLabel = `${now.getMonth() + 1}월 ${now.getDate()}일`

// 주제 고르기 (주제가 있는 목록만)
const cat = ref('전체')
const cats = c.list[0].cat ? [['전체', c.list.length], ...[...new Set(c.list.map(x => x.cat))].map(k => [k, c.list.filter(x => x.cat === k).length])] : null
const pool = computed(() => cat.value === '전체' ? c.list : c.list.filter(x => x.cat === cat.value))
function other(list, curItem) { if (list.length < 2) return list[0]; let x; do { x = list[Math.floor(Math.random() * list.length)] } while (x === curItem); return x }
const cur = ref(other(c.list, daily))
const hold = ref(false)
watch(cat, () => { hold.value = false; cur.value = other(pool.value, cur.value) })

const pulse = ref(false); let pulseT = null
const floats = ref([]); let floatSeq = 0
function hit() {
  const before = p.today.value
  p.hit()
  if (p.rec.value.sound) c.play()
  if (!hold.value) cur.value = other(pool.value, cur.value)
  pulse.value = false; clearTimeout(pulseT)
  requestAnimationFrame(() => { pulse.value = true; pulseT = setTimeout(() => (pulse.value = false), props.part === 'bell' ? 900 : 140) })
  const id = ++floatSeq; floats.value = [...floats.value.slice(-5), id]; setTimeout(() => (floats.value = floats.value.filter(x => x !== id)), 700)
  try { navigator.vibrate?.(8) } catch { /* 진동 없는 기기 */ }
  if (before < goal.value && before + 1 >= goal.value) { auto.value = false; toast('오늘 목표를 채웠습니다', 'ok') }
}
const bead = computed(() => p.today.value % 108)

// 자동 두드림·자동 울림
const auto = ref(false); const speed = ref(c.speeds ? (props.part === 'moktak' ? 1 : 0) : 0); let autoT = null
watch([auto, speed], () => { clearInterval(autoT); if (auto.value) autoT = setInterval(hit, c.speeds[speed.value][1]) })

// 숨 고르기: 4초 들이쉬고 6초 내쉰다 (동그라미 움직임은 CSS 가 맡는다)
const breath = ref(false); const breathIn = ref(true); let breathT = null
watch(breath, on => {
  clearTimeout(breathT); breathIn.value = true
  const turn = () => { breathT = setTimeout(() => { breathIn.value = !breathIn.value; turn() }, breathIn.value ? 4000 : 6000) }
  if (on) turn()
})

// 명상 타이머
const mins = ref(5); const remain = ref(null); let clockT = null
function toggleTimer() {
  clearInterval(clockT)
  if (remain.value !== null) { remain.value = null; return }
  const end = Date.now() + mins.value * 60000
  remain.value = mins.value * 60
  clockT = setInterval(() => {
    remain.value = Math.max(0, Math.round((end - Date.now()) / 1000))
    if (remain.value > 0) return
    clearInterval(clockT); remain.value = null; auto.value = false
    if (p.rec.value.sound) [0, 0.7, 1.4].forEach(t => knock(t))
    toast(`${mins.value}분 명상을 마쳤습니다`, 'ok')
  }, 500)
}

// 멜로디
const mel = ref(0); const stopMelody = ref(null)
function toggleMelody() {
  if (stopMelody.value) { stopMelody.value(); stopMelody.value = null; return }
  const m = MELODIES[mel.value]; stopMelody.value = playMelody(m.notes, m.beat)
}
function pickMelody(i) { mel.value = i; if (stopMelody.value) { toggleMelody(); toggleMelody() } }

// 말씀 찾기
const q = ref('')
const found = computed(() => { const s = q.value.trim(); return s ? VERSES.filter(x => x.t.includes(s) || x.src.includes(s) || x.cat.includes(s)).slice(0, 30) : [] })

function stay(x) { cur.value = x; hold.value = true; toast('이 구절에 머뭅니다', 'ok') }
const favs = computed(() => p.rec.value.favs.map(t => c.list.find(x => x.t === t)).filter(Boolean))
function text(x) { return [x.t, x.s, '— ' + x.src].filter(Boolean).join('\n') }
async function copy(s, done) {
  try { await navigator.clipboard.writeText(s); toast(done, 'ok') } catch {
    const ta = document.createElement('textarea'); ta.value = s; document.body.appendChild(ta); ta.select()
    try { document.execCommand('copy'); toast(done, 'ok') } catch { toast('복사하지 못했습니다') } finally { ta.remove() }
  }
}

const canSpeak = typeof window !== 'undefined' && 'speechSynthesis' in window; const speaking = ref(false)
function speak() {
  speechSynthesis.cancel()
  if (speaking.value) { speaking.value = false; return }
  const u = new SpeechSynthesisUtterance(cur.value.t); u.lang = 'ko-KR'; u.rate = 0.9
  u.onend = u.onerror = () => (speaking.value = false)
  speaking.value = true; speechSynthesis.speak(u)
}

// 지금 구절을 정사각형 그림으로 내려받는다
function saveImage() {
  const S = 1080; const cv = document.createElement('canvas'); cv.width = cv.height = S
  const g = cv.getContext('2d'); const x = cur.value; const font = '"Noto Serif KR", "Nanum Myeongjo", serif'
  g.fillStyle = '#faf7f0'; g.fillRect(0, 0, S, S); g.fillStyle = c.color; g.fillRect(90, 150, 8, S - 300)
  const wrap = (s, size, weight) => { g.font = `${weight} ${size}px ${font}`; const out = []; let line = ''
    for (const ch of s) { if (g.measureText(line + ch).width > S - 300 && line) { out.push(line); line = ch.trimStart() } else line += ch }
    if (line) out.push(line); return out.map(t => ({ t, size, weight })) }
  const big = x.t.length > 90 ? 44 : x.t.length > 40 ? 54 : 68
  const lines = [...wrap(x.t, big, 700), ...(x.s ? [{ gap: 30 }, ...wrap(x.s, 36, 400)] : []), { gap: 50 }, { t: '— ' + x.src, size: 30, weight: 400, soft: true }]
  let y = (S - lines.reduce((a, l) => a + (l.gap || l.size * 1.55), 0)) / 2
  g.textBaseline = 'top'
  for (const l of lines) {
    if (l.gap) { y += l.gap; continue }
    g.font = `${l.weight} ${l.size}px ${font}`; g.fillStyle = l.soft ? c.color : l.size < big ? '#555' : '#1c1c1c'; g.fillText(l.t, 140, y); y += l.size * 1.55
  }
  g.font = `400 24px ${font}`; g.fillStyle = '#999'; g.fillText(`심법 · ${c.title}`, 140, S - 110)
  cv.toBlob(b => { if (!b) return toast('그림을 만들지 못했습니다'); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = `simbeop-${props.part}.png`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000) })
}

const asking = ref(false); let askT = null
function resetAsk() {
  clearTimeout(askT)
  if (asking.value) { p.reset(); asking.value = false; toast('기록을 지웠습니다', 'ok'); return }
  asking.value = true; askT = setTimeout(() => (asking.value = false), 3000)
}

function onKey(e) {
  if (e.code !== 'Space' || e.repeat || /^(INPUT|TEXTAREA|BUTTON|SELECT|SUMMARY|A)$/.test(e.target.tagName)) return
  e.preventDefault(); hit()
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  ;[autoT, clockT].forEach(clearInterval); [pulseT, breathT, askT].forEach(clearTimeout)
  if (stopMelody.value) stopMelody.value()
  if (canSpeak) speechSynthesis.cancel()
})
</script>

<style scoped>
/* --sb 는 화면별 강조색. 글자·알에는 본문색을 섞은 --sb-ink 를 써서 어두운 화면에서도 읽히게 한다 */
.sb { --sb-ink: color-mix(in srgb, var(--sb) 62%, var(--text)); min-width: 0; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; max-width: 560px; }
.main, .side { display: contents; }
.head, .center { text-align: center; } .head h1 { font-size: 24px; } .head { order: 0; }
/* 좁은 화면 순서: 통계 → 목표 → 주제 → 누르는 곳 → 구절 → 버튼 → 오늘의 구절 → 나머지 */
.stats { order: 1; } .goalbox { order: 2; } .cats { order: 3; } .main > * { order: 5; } .main > .cats { order: 3; } .side > * { order: 8; } .side > .stats { order: 1; } .side > .goalbox { order: 2; } .foot { order: 9; }
.han { font-family: "Noto Serif KR", "Nanum Myeongjo", serif; letter-spacing: .06em; }
.daily { border-left: 3px solid var(--sb-ink); padding: 4px 0 4px 12px; display: flex; flex-direction: column; gap: 3px; }
.daily .lab { color: var(--sb-ink); font-weight: 700; } .d-t { font-size: 16px; line-height: 1.6; word-break: keep-all; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.stats div { display: flex; flex-direction: column; align-items: center; padding: 10px 4px; } .stats div + div { border-left: 1px solid var(--line); }
.stats b { font-size: 22px; font-variant-numeric: tabular-nums; } .stats span { font-size: 11px; color: var(--muted); }
.bump { animation: bump .25s ease-out; }
.goalbox { display: flex; flex-direction: column; gap: 6px; }
.goal { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
.goals button { padding: 2px 7px; font-size: 12px; color: var(--muted); border-radius: 0; border-bottom: 2px solid transparent; }
.goals button.on { color: var(--text); font-weight: 700; border-bottom-color: var(--sb-ink); }
.bar-fg { background: var(--sb-ink); transition: width .25s; }
.cats, .acts { display: flex; gap: 6px; flex-wrap: wrap; justify-content: center; }
.cats button, .acts button:not(.primary) { border-radius: 999px; padding: 5px 12px; font-size: 12px; white-space: nowrap; }
.cats button.on, .acts button.on { background: var(--sb); border-color: var(--sb); color: #fff; }
.acts button.primary, .sec > button.primary { background: var(--sb); border-color: var(--sb); border-radius: 999px; }
.acts button:disabled { opacity: .5; cursor: default; }
.stage { position: relative; align-self: center; display: flex; justify-content: center; }
.inst { border: 0; background: none; padding: 6px; border-radius: 50%; cursor: pointer; touch-action: manipulation; transition: transform .1s; -webkit-tap-highlight-color: transparent; position: relative; }
.inst:hover { background: none; } .inst svg { display: block; }
.inst.sayings svg { width: 124px; } .inst.moktak svg { width: 270px; } .inst.bell svg { width: 170px; }
.inst.sayings { filter: drop-shadow(0 4px 8px rgba(0, 0, 0, .2)); } .inst.sayings.hit { transform: scale(.9) rotate(-4deg); filter: none; }
.inst.moktak .mallet { transform-origin: 236px 44px; transition: transform .1s; } .inst.moktak.hit .mallet { transform: rotate(16deg); }
.inst.moktak.hit { transform: scale(.985); }
.inst.bell { transform-origin: 50% 8%; } .inst.bell.hit { animation: swing .9s ease-out; }
.halo { position: absolute; left: 50%; top: 50%; width: 150px; height: 150px; margin: -75px 0 0 -75px; border-radius: 50%; background: var(--sb-ink); opacity: .16; animation: breathe 10s ease-in-out infinite; pointer-events: none; }
.plus { position: absolute; left: 50%; top: 18%; font-weight: 800; font-size: 18px; color: var(--sb-ink); pointer-events: none; animation: rise .7s ease-out forwards; }
.verse { position: relative; padding: 22px 18px; min-height: 132px; display: flex; flex-direction: column; justify-content: center; overflow: hidden; }
.v-t { font-size: 19px; font-weight: 700; line-height: 1.6; word-break: keep-all; } .v-t.han { font-size: 26px; font-weight: 500; }
.v-s { font-size: 14px; line-height: 1.6; margin-top: 8px; word-break: keep-all; }
.v-f { display: flex; justify-content: space-between; gap: 8px; margin-top: 12px; } .src { color: var(--sb-ink); white-space: nowrap; }
.seal { position: absolute; right: 12px; top: 10px; width: 46px; height: 46px; border: 2px solid var(--sb-ink); color: var(--sb-ink); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 800; opacity: .3; transform: rotate(-14deg); animation: press .3s ease-out; }
.hint { margin-top: -4px; }
.sec { border-top: 1px solid var(--line); padding-top: 14px; } .sec.center { display: flex; flex-direction: column; align-items: center; gap: 10px; }
.sec h3 { margin: 0; font-size: 15px; } .sec summary { font-weight: 700; cursor: pointer; }
.clock { font-size: 34px; font-weight: 800; font-variant-numeric: tabular-nums; line-height: 1; }
.row-b { display: flex; justify-content: space-between; gap: 10px; align-items: baseline; width: 100%; text-align: left; border: 0; border-bottom: 1px solid var(--line); border-radius: 0; padding: 8px 2px; font-size: 13px; line-height: 1.5; background: none; }
.fav { display: flex; align-items: center; gap: 4px; }
.heat { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); grid-template-rows: repeat(7, auto); grid-auto-flow: column; gap: 3px; max-width: 340px; }
.hc { aspect-ratio: 1; border-radius: 3px; background: var(--panel-2); border: 1px solid var(--line); }
.hc.l1 { background: color-mix(in srgb, var(--sb-ink) 25%, var(--panel)); } .hc.l2 { background: color-mix(in srgb, var(--sb-ink) 45%, var(--panel)); }
.hc.l3 { background: color-mix(in srgb, var(--sb-ink) 70%, var(--panel)); } .hc.l4 { background: var(--sb-ink); }
.hc.fut { visibility: hidden; } .hc.now { outline: 2px solid var(--text); outline-offset: -1px; }
.h-f { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; margin: 8px 0 4px; max-width: 340px; } .lg { display: inline-flex; align-items: center; gap: 3px; } .lg .hc { width: 10px; display: inline-block; }
.foot { display: flex; flex-direction: column; gap: 4px; padding-bottom: 20px; }
.fade { animation: fade .45s ease-out; }
@keyframes swing { 0% { transform: rotate(0) } 20% { transform: rotate(8deg) } 45% { transform: rotate(-6deg) } 70% { transform: rotate(3deg) } 100% { transform: rotate(0) } }
@keyframes breathe { 0% { transform: scale(.7) } 40% { transform: scale(1.75) } 100% { transform: scale(.7) } }
@keyframes fade { from { opacity: 0; transform: translateY(6px) } to { opacity: 1; transform: none } }
@keyframes rise { from { opacity: .95; transform: translate(-50%, 0) } to { opacity: 0; transform: translate(-50%, -46px) } }
@keyframes bump { from { transform: scale(1.25) } to { transform: none } }
@keyframes press { from { opacity: .7; transform: rotate(-14deg) scale(1.5) } to { opacity: .3; transform: rotate(-14deg) scale(1) } }
/* 좁은 화면: 누르는 곳과 구절이 한 화면에 들어오게 줄인다 */
@media (max-width: 700px) {
  .cats { flex-wrap: nowrap; justify-content: flex-start; overflow-x: auto; padding-bottom: 2px; scrollbar-width: none; }
  .inst.moktak svg { width: 210px; } .inst.bell svg { width: 132px; } .inst.sayings svg { width: 104px; }
  .head h1 { font-size: 20px; } .stats div { padding: 6px 4px; } .stats b { font-size: 19px; } .sb { gap: 11px; }
  .verse { min-height: 110px; padding: 16px 14px; } .heat, .h-f { max-width: none; }
}
/* 넓은 화면: 왼쪽에 누르는 곳, 오른쪽에 통계와 기록 */
@media (min-width: 1100px) {
  .sb { display: grid; grid-template-columns: minmax(0, 480px) minmax(0, 380px); column-gap: 44px; max-width: 920px; align-items: start; }
  .head { grid-column: 1 / -1; }
  .main, .side { display: flex; flex-direction: column; gap: 14px; min-width: 0; } .main > *, .side > * { order: 0 !important; }
  .main { position: sticky; top: 8px; } .side .sec:first-of-type { border-top: 0; padding-top: 0; }
}
@media (prefers-reduced-motion: reduce) { .inst.bell.hit, .fade, .halo, .plus, .bump, .seal { animation: none } .plus { display: none } }
</style>
