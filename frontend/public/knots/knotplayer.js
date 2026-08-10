/* ═══════════════════════════════════════════════════════════════════════
   knotplayer.js — MYK KnotPlayer Motor
   Sürüm: Sprint 2
   Bağımlılık: AnimationAdapter implementasyonu (anime-adapter.js vb.)
   Kullanım:
     const kp = KnotPlayer.init('kp', { adapter: 'anime' })
   ═══════════════════════════════════════════════════════════════════════ */

'use strict';

const KnotPlayer = (() => {

  /* ── Sabitler ─────────────────────────────────────────────────────── */
  const SPEEDS = [0.5, 1, 1.5, 2];
  const DEFAULT_STEP_DURATION_MS = 1800; // ses yokken adım başı süre (1× hızda)

  /* ── AnimationAdapter Sözleşmesi (interface dokümantasyonu) ──────────
   *
   * class AnimationAdapter {
   *   constructor(svgEl, timeline) {}
   *   async renderStep(stepIndex, options = {})  // adımı çiz
   *   seek(stepIndex, progress)                  // 0.0–1.0 adım içi konum
   *   setSpeed(multiplier)                       // 0.5, 1, 1.5, 2
   *   pause()
   *   resume()
   *   cancelCurrent()
   *   destroy()
   * }
   * ─────────────────────────────────────────────────────────────────── */

  /* ── AdapterRegistry ─────────────────────────────────────────────── */
  const _adapters = {};
  function registerAdapter(name, AdapterClass) {
    _adapters[name] = AdapterClass;
  }

  /* ── Clock Soyutlaması ───────────────────────────────────────────── */
  /**
   * PerformanceClock: ses yokken performance.now() tabanlı saat.
   * AudioClock: ses varsa AudioContext.currentTime tabanlı saat.
   * Her ikisi de .now() → ms döner.
   */
  class PerformanceClock {
    constructor() { this._offset = 0; this._paused = true; this._pausedAt = 0; }
    start()  { if (this._paused) { this._offset = performance.now() - this._pausedAt; this._paused = false; } }
    pause()  { if (!this._paused) { this._pausedAt = this.now(); this._paused = true; } }
    reset()  { this._offset = 0; this._pausedAt = 0; this._paused = true; }
    seekMs(ms) { this._pausedAt = ms; if (!this._paused) { this._offset = performance.now() - ms; } }
    now()    { return this._paused ? this._pausedAt : performance.now() - this._offset; }
    get paused() { return this._paused; }
  }

  class AudioClock {
    constructor(audioEl) { this._audio = audioEl; }
    start()    { this._audio.play().catch(() => {}); }
    pause()    { this._audio.pause(); }
    reset()    { this._audio.currentTime = 0; }
    seekMs(ms) { this._audio.currentTime = ms / 1000; }
    now()      { return this._audio.currentTime * 1000; }
    get paused() { return this._audio.paused; }
  }

  /* ── KnotPlayerInstance ──────────────────────────────────────────── */
  function createInstance(containerId, options = {}) {
    const container = typeof containerId === 'string'
      ? document.getElementById(containerId)
      : containerId;
    if (!container) throw new Error(`KnotPlayer: container '${containerId}' bulunamadı`);

    /* -- Durum -- */
    let timeline   = null;
    let adapter    = null;
    let clock      = null;
    let audioEl    = null;
    let _step      = 0;       // 0-based
    let _playing   = false;
    let _audioOn   = false;
    let _speed     = 1;
    let _completed = false;
    let _rafId     = null;
    let _autoTimer = null;    // ses yokken adım geçiş zamanlayıcısı

    /* -- DOM referansları -- */
    const svgEl      = () => container.querySelector('.kp-stage');
    const stepsBar   = () => container.querySelector('.kp-steps-bar');
    const descEl     = () => container.querySelector('.kp-desc-text');
    const numEl      = () => container.querySelector('.kp-step-num');
    const playBtn    = () => container.querySelector('[data-action="play"]');
    const audioBar   = () => container.querySelector('.kp-audio-bar');
    const doneBanner = () => container.querySelector('.kp-done-banner');
    const errorEl    = () => container.querySelector('.kp-error');

    /* ── Olay Yayıcı ─────────────────────────────────────────────── */
    function emit(name, detail = {}) {
      container.dispatchEvent(new CustomEvent(`kp:${name}`, { detail, bubbles: true }));
    }

    /* ── Timeline Yükleme ────────────────────────────────────────── */
    async function loadTimeline() {
      const url = container.dataset.timeline;
      if (!url) throw new Error('KnotPlayer: data-timeline attr eksik');

      const res = await fetch(url, { credentials: 'same-origin', cache: 'no-cache' });
      if (!res.ok) throw new Error(`Timeline yüklenemedi: HTTP ${res.status}`);
      const data = await res.json();

      if (!data.slug || !data.version || !Array.isArray(data.steps) || data.steps.length === 0) {
        throw new Error('Timeline şema hatası: slug, version veya steps eksik');
      }
      return data;
    }

    /* ── Ses Kurulumu ────────────────────────────────────────────── */
    function setupAudio(src) {
      if (!src) return null;
      const el = document.createElement('audio');
      el.preload = 'none';
      el.style.display = 'none';
      const source = document.createElement('source');
      source.src = src;
      source.type = 'audio/mpeg';
      el.appendChild(source);
      container.appendChild(el);

      el.addEventListener('playing', () => audioBar()?.classList.add('visible'));
      el.addEventListener('pause',   () => audioBar()?.classList.remove('visible'));
      el.addEventListener('ended',   () => audioBar()?.classList.remove('visible'));
      el.addEventListener('error',   () => {
        const btn = container.querySelector('[data-action="audio"]');
        if (btn) { btn.disabled = true; btn.title = 'Ses dosyası bulunamadı'; }
      });
      el.load();
      return el;
    }

    /* ── Adım Çubuğu ─────────────────────────────────────────────── */
    function buildStepsBar() {
      const bar = stepsBar();
      if (!bar) return;
      bar.innerHTML = '';
      bar.setAttribute('role', 'tablist');

      for (let i = 0; i < timeline.steps.length; i++) {
        if (i > 0) {
          const conn = document.createElement('div');
          conn.className = 'kp-step-conn';
          conn.id = `kp-conn-${i}`;
          bar.appendChild(conn);
        }
        const dot = document.createElement('button');
        dot.className = 'kp-step-dot';
        dot.id = `kp-dot-${i}`;
        dot.textContent = i + 1;
        dot.setAttribute('aria-label', `Adım ${i + 1}: ${timeline.steps[i].title}`);
        dot.setAttribute('role', 'tab');
        dot.addEventListener('click', () => { pausePlayback(); goTo(i); });
        bar.appendChild(dot);
      }
      const lbl = document.createElement('span');
      lbl.className = 'kp-step-label';
      lbl.id = 'kp-step-label';
      bar.appendChild(lbl);
    }

    /* ── Adım Güncelleme ─────────────────────────────────────────── */
    const _seen = new Set();

    function goTo(n, skipReport = false) {
      n = Math.max(0, Math.min(n, timeline.steps.length - 1));
      _step = n;

      const sg = svgEl();
      const de = descEl();
      if (!sg || !de) return;

      sg.classList.add('fading');
      de.classList.add('fading');

      setTimeout(() => {
        // Adapter'a çiz
        if (adapter) {
          adapter.cancelCurrent();
          adapter.renderStep(n).catch(() => {});
        }

        // Açıklama
        const step = timeline.steps[n];
        de.textContent = step.description;
        de.classList.remove('fading');
        sg.classList.remove('fading');
        if (numEl()) numEl().textContent = n + 1;

        // Adım sayacı etiketi
        const lbl = document.getElementById('kp-step-label');
        if (lbl) lbl.textContent = `${n + 1} / ${timeline.steps.length}`;

        // Dot güncellemesi
        updateStepsBar(n);
        updateControls();

        // Ses senkronu
        if (_audioOn && clock instanceof AudioClock) {
          clock.seekMs(step.audio_range[0]);
          if (_playing) clock.start();
        }

        // İlerleme olayı — her yeni adım için bir kez
        if (!skipReport) {
          _seen.add(n);
          emit('step', { step: n + 1, total: timeline.steps.length });
        }

        // Tamamlandı?
        if (n === timeline.steps.length - 1 && !_completed) {
          _completed = true;
          setTimeout(() => {
            doneBanner()?.classList.add('show');
            emit('complete');
          }, 800);
        }
      }, 175);
    }

    function updateStepsBar(cur) {
      for (let i = 0; i < timeline.steps.length; i++) {
        const dot  = document.getElementById(`kp-dot-${i}`);
        const conn = document.getElementById(`kp-conn-${i}`);
        if (!dot) continue;
        dot.classList.remove('active', 'done');
        dot.setAttribute('aria-selected', i === cur ? 'true' : 'false');
        if (i === cur) dot.classList.add('active');
        else if (_seen.has(i)) dot.classList.add('done');
        if (conn) conn.classList.toggle('done', _seen.has(i) && i <= cur);
      }
    }

    function updateControls() {
      const first = container.querySelector('[data-action="first"]');
      const prev  = container.querySelector('[data-action="previous"]');
      const next  = container.querySelector('[data-action="next"]');
      const last  = container.querySelector('[data-action="last"]');
      const play  = playBtn();

      if (first) first.disabled = _step === 0;
      if (prev)  prev.disabled  = _step === 0;
      if (next)  next.disabled  = _step === timeline.steps.length - 1;
      if (last)  last.disabled  = _step === timeline.steps.length - 1;
      if (play) {
        play.textContent = _playing ? '⏸' : '▶';
        play.setAttribute('aria-label', _playing ? 'Duraklat' : 'Oynat');
        play.title = _playing ? 'Duraklat (Boşluk)' : 'Oynat (Boşluk)';
      }
    }

    /* ── Oynatma ─────────────────────────────────────────────────── */
    function startPlayback() {
      if (_step >= timeline.steps.length - 1) goTo(0, true);
      _playing = true;
      updateControls();

      if (clock instanceof AudioClock && _audioOn) {
        clock.seekMs(timeline.steps[_step].audio_range[0]);
        clock.start();
        // RAF döngüsü ses ile adım senkronu için
        scheduleRAF();
      } else {
        // Ses yok: setTimeout tabanlı adım geçişi
        clock.start();
        scheduleAutoAdvance();
      }
    }

    function pausePlayback() {
      _playing = false;
      clock.pause();
      cancelAutoAdvance();
      cancelRAF();
      if (adapter) adapter.pause();
      updateControls();
      emit('pause');
    }

    function scheduleAutoAdvance() {
      cancelAutoAdvance();
      if (!_playing || _step >= timeline.steps.length - 1) return;
      const stepMs = DEFAULT_STEP_DURATION_MS / _speed;
      _autoTimer = setTimeout(() => {
        if (!_playing) return;
        if (_step < timeline.steps.length - 1) {
          goTo(_step + 1);
          scheduleAutoAdvance();
        } else {
          _playing = false;
          updateControls();
        }
      }, stepMs);
    }

    function cancelAutoAdvance() {
      if (_autoTimer !== null) { clearTimeout(_autoTimer); _autoTimer = null; }
    }

    /* RAF döngüsü: AudioClock → adım güncelleme */
    function scheduleRAF() {
      cancelRAF();
      function tick() {
        if (!_playing) return;
        const now = clock.now();
        const step = timeline.steps[_step];
        if (now >= step.audio_range[1]) {
          const next = _step + 1;
          if (next < timeline.steps.length) {
            goTo(next, false);
            _rafId = requestAnimationFrame(tick);
          } else {
            _playing = false;
            updateControls();
          }
        } else {
          _rafId = requestAnimationFrame(tick);
        }
      }
      _rafId = requestAnimationFrame(tick);
    }

    function cancelRAF() {
      if (_rafId !== null) { cancelAnimationFrame(_rafId); _rafId = null; }
    }

    /* ── Public API ──────────────────────────────────────────────── */
    const api = {
      play() {
        if (_playing) return;
        emit('play');
        startPlayback();
      },
      pause() {
        if (!_playing) return;
        pausePlayback();
      },
      restart() {
        pausePlayback();
        _completed = false;
        _seen.clear();
        doneBanner()?.classList.remove('show');
        clock.reset();
        goTo(0);
      },
      next() {
        pausePlayback();
        goTo(_step + 1);
      },
      previous() {
        pausePlayback();
        goTo(_step - 1);
      },
      seekStep(index) {
        pausePlayback();
        goTo(index);
      },
      seekTime(ms) {
        // ms konumuna göre adımı bul ve adapter.seek() çağır
        let target = timeline.steps.length - 1;
        for (let i = 0; i < timeline.steps.length; i++) {
          const [s, e] = timeline.steps[i].audio_range;
          if (ms >= s && ms < e) { target = i; break; }
        }
        const [s, e] = timeline.steps[target].audio_range;
        const progress = Math.max(0, Math.min(1, (ms - s) / (e - s)));
        pausePlayback();
        goTo(target, true);
        if (adapter) adapter.seek(target, progress);
      },
      setSpeed(multiplier) {
        _speed = multiplier;
        if (adapter) adapter.setSpeed(multiplier);
        if (_playing && !(_audioOn && clock instanceof AudioClock)) {
          cancelAutoAdvance();
          scheduleAutoAdvance();
        }
      },
      toggleAudio() {
        if (!audioEl) return;
        _audioOn = !_audioOn;
        const btn = container.querySelector('[data-action="audio"]');
        if (btn) {
          btn.textContent = _audioOn ? '🔊' : '🔈';
          btn.classList.toggle('on', _audioOn);
        }
        if (!_audioOn) {
          audioEl.pause();
          // AudioClock → PerformanceClock'a geç
          if (clock instanceof AudioClock) {
            const pos = clock.now();
            clock = new PerformanceClock();
            clock.seekMs(pos);
          }
        } else {
          // PerformanceClock → AudioClock'a geç
          clock = new AudioClock(audioEl);
          if (_playing) {
            clock.seekMs(timeline.steps[_step].audio_range[0]);
            clock.start();
          }
        }
      },
      getState() {
        return {
          step: _step,
          total: timeline ? timeline.steps.length : 0,
          playing: _playing,
          audioOn: _audioOn,
          speed: _speed,
          completed: _completed,
        };
      },
      destroy() {
        pausePlayback();
        if (adapter) adapter.destroy();
        if (audioEl) audioEl.remove();
        container.innerHTML = '';
      },
    };

    /* ── Klavye ──────────────────────────────────────────────────── */
    function handleKeydown(e) {
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;
      switch (e.key) {
        case 'ArrowRight':
        case 'ArrowDown':  e.preventDefault(); api.next(); break;
        case 'ArrowLeft':
        case 'ArrowUp':    e.preventDefault(); api.previous(); break;
        case ' ':          e.preventDefault(); _playing ? api.pause() : api.play(); break;
        case 'Home':       e.preventDefault(); api.seekStep(0); break;
        case 'End':        e.preventDefault(); api.seekStep(timeline.steps.length - 1); break;
      }
    }

    /* ── Kontrol Bağlama ─────────────────────────────────────────── */
    function bindControls() {
      container.querySelectorAll('[data-action]').forEach(btn => {
        const action = btn.dataset.action;
        btn.addEventListener('click', () => {
          switch (action) {
            case 'first':    pausePlayback(); goTo(0); break;
            case 'previous': pausePlayback(); goTo(_step - 1); break;
            case 'play':     _playing ? api.pause() : api.play(); break;
            case 'next':     pausePlayback(); goTo(_step + 1); break;
            case 'last':     pausePlayback(); goTo(timeline.steps.length - 1); break;
            case 'audio':    api.toggleAudio(); break;
          }
        });
      });

      const speedSel = container.querySelector('.kp-speed-sel');
      if (speedSel) {
        speedSel.addEventListener('change', () => {
          api.setSpeed(parseFloat(speedSel.value));
        });
      }

      document.addEventListener('keydown', handleKeydown);
    }

    /* ── Hata Gösterimi ──────────────────────────────────────────── */
    function showError(msg) {
      const el = errorEl();
      if (el) {
        el.innerHTML = `<div class="kp-error-icon">⚠️</div>
          <div>Bu eğitim içeriği şu anda yüklenemiyor.</div>`;
        el.classList.add('show');
      }
      emit('error', { message: msg });
    }

    /* ── Başlatıcı ───────────────────────────────────────────────── */
    async function init() {
      try {
        timeline = await loadTimeline();
      } catch (err) {
        showError(err.message);
        return api;
      }

      // Ses kurulumu
      if (timeline.audio) {
        audioEl = setupAudio(timeline.audio);
        clock   = new AudioClock(audioEl);
      } else {
        container.classList.add('kp--no-audio');
        clock = new PerformanceClock();
        const btn = container.querySelector('[data-action="audio"]');
        if (btn) { btn.disabled = true; btn.title = 'Ses dosyası henüz eklenmedi'; }
      }

      // Adapter seçimi
      const adapterName = options.adapter || 'anime';
      const AdapterClass = _adapters[adapterName];
      if (!AdapterClass) {
        showError(`Adapter bulunamadı: '${adapterName}'. Önce registerAdapter() çağırın.`);
        return api;
      }

      const sg = svgEl();
      if (!sg) {
        showError('SVG alanı (.kp-stage) bulunamadı');
        return api;
      }

      // viewBox ayarla
      sg.setAttribute('viewBox', timeline.viewBox || '0 0 480 290');
      sg.setAttribute('aria-label', `${timeline.title} bağı animasyonu`);

      adapter = new AdapterClass(sg, timeline);
      adapter.setSpeed(_speed);

      buildStepsBar();
      bindControls();
      goTo(0, true);

      emit('ready', { slug: timeline.slug, steps: timeline.steps.length });
    }

    init();
    return api;
  }

  /* ── Public ─────────────────────────────────────────────────────── */
  return {
    init: createInstance,
    registerAdapter,
  };

})();

/* Export (module ortamı için) */
if (typeof module !== 'undefined' && module.exports) {
  module.exports = KnotPlayer;
}
