/* ═══════════════════════════════════════════════════════════════════════
   anime-adapter.js — Anime.js AnimationAdapter implementasyonu
   Sürüm: Sprint 2
   Bağımlılık: /static/vendor/anime/anime.min.js (window.anime)
   Kayıt: KnotPlayer.registerAdapter('anime', AnimeAdapter)
   ═══════════════════════════════════════════════════════════════════════ */

'use strict';

class AnimeAdapter {

  /**
   * @param {SVGElement} svgEl  — .kp-stage SVG elementi
   * @param {Object}     tl     — timeline.json verisi
   */
  constructor(svgEl, tl) {
    this._svg      = svgEl;
    this._tl       = tl;
    this._speed    = 1;
    this._current  = null;   // devam eden anime instance
    this._colors   = tl.colors || {};
  }

  /* ── Renk Token → Değer ──────────────────────────────────────────── */
  _resolveColor(token) {
    return this._colors[token] || token;
  }

  /* ── Adımı Çiz ───────────────────────────────────────────────────── */
  async renderStep(stepIndex) {
    this.cancelCurrent();

    const step = this._tl.steps[stepIndex];
    if (!step) return;

    this._svg.innerHTML = '';

    const drawDuration = (780 / this._speed);
    const labelDelay   = 600 / this._speed;

    const sortedPaths = [...step.paths].sort((a, b) => (a.layer || 0) - (b.layer || 0));

    sortedPaths.filter(p => !p.animated).forEach(pd => {
      this._svg.appendChild(this._buildPathEl(pd, false));
    });

    const animatedPaths = sortedPaths.filter(p => p.animated);
    const pathEls = animatedPaths.map(pd => {
      const el = this._buildPathEl(pd, true);
      this._svg.appendChild(el);
      return el;
    });

    if (step.labels) {
      step.labels.forEach(lbl => this._svg.appendChild(this._buildLabelEl(lbl, labelDelay)));
    }

    if (pathEls.length > 0 && typeof anime !== 'undefined') {
      this._current = anime({
        targets: pathEls,
        strokeDashoffset: [1, 0],
        easing: 'cubicBezier(.35, 0, .15, 1)',
        duration: drawDuration,
        delay: anime.stagger(120 / this._speed),
        autoplay: true,
      });
    } else if (pathEls.length > 0) {
      pathEls.forEach(el => {
        el.style.transition = `stroke-dashoffset ${drawDuration}ms cubic-bezier(.35,0,.15,1)`;
        requestAnimationFrame(() => requestAnimationFrame(() => {
          el.style.strokeDashoffset = '0';
        }));
      });
    }
  }

  /* ── Path SVGElement Üret ────────────────────────────────────────── */
  _buildPathEl(pd, animated) {
    const ns = 'http://www.w3.org/2000/svg';
    const isLine = pd.d && pd.d.match(/^M[\d.,\s]+L[\d.,\s]+$/);
    const el = document.createElementNS(ns, isLine ? 'line' : 'path');

    if (isLine) {
      const coords = pd.d.match(/[\d.]+/g);
      if (coords && coords.length >= 4) {
        el.setAttribute('x1', coords[0]);
        el.setAttribute('y1', coords[1]);
        el.setAttribute('x2', coords[2]);
        el.setAttribute('y2', coords[3]);
      }
    } else {
      el.setAttribute('d', pd.d);
    }

    el.setAttribute('stroke',         this._resolveColor(pd.stroke || 'rope_main'));
    el.setAttribute('stroke-width',   pd.stroke_width  || 6);
    el.setAttribute('stroke-linecap', pd.stroke_linecap || 'round');
    if (pd.stroke_linejoin) el.setAttribute('stroke-linejoin', pd.stroke_linejoin);
    el.setAttribute('fill',           pd.fill || 'none');
    if (pd.opacity !== undefined) el.setAttribute('opacity', pd.opacity);

    if (animated) {
      el.setAttribute('pathLength',         '1');
      el.style.strokeDasharray  = '1';
      el.style.strokeDashoffset = '1';
    }

    if (pd.id) el.setAttribute('id', `kp-p-${pd.id}`);
    return el;
  }

  /* ── Label SVGElement Üret ───────────────────────────────────────── */
  _buildLabelEl(lbl, baseDelay) {
    const ns = 'http://www.w3.org/2000/svg';
    const el = document.createElementNS(ns, 'text');

    el.setAttribute('x',           lbl.x);
    el.setAttribute('y',           lbl.y);
    el.setAttribute('fill',        lbl.fill || 'rgba(232,244,255,.5)');
    el.setAttribute('font-size',   lbl.font_size || 11);
    if (lbl.text_anchor)  el.setAttribute('text-anchor',  lbl.text_anchor);
    if (lbl.font_weight)  el.setAttribute('font-weight',  lbl.font_weight);
    el.textContent = lbl.text;

    const delay = (lbl.delay_ms || 0) / this._speed;
    el.style.opacity = '0';
    el.style.animation = `kp-fi ${400 / this._speed}ms ease ${delay}ms forwards`;

    if (lbl.id) el.setAttribute('id', `kp-l-${lbl.id}`);
    return el;
  }

  /* ── seek(stepIndex, progress) ───────────────────────────────────── */
  seek(stepIndex, progress) {
    this.cancelCurrent();
    const step = this._tl.steps[stepIndex];
    if (!step) return;

    this._svg.innerHTML = '';

    const sortedPaths = [...step.paths].sort((a, b) => (a.layer || 0) - (b.layer || 0));

    sortedPaths.forEach(pd => {
      const el = this._buildPathEl(pd, false);
      if (pd.animated) {
        el.setAttribute('pathLength', '1');
        el.style.strokeDasharray  = '1';
        el.style.strokeDashoffset = String(Math.max(0, 1 - progress));
      }
      this._svg.appendChild(el);
    });

    if (step.labels && progress > 0.5) {
      step.labels.forEach(lbl => {
        const el = this._buildLabelEl(lbl, 0);
        el.style.animation = 'none';
        el.style.opacity   = String(Math.min(1, (progress - 0.5) * 2));
        this._svg.appendChild(el);
      });
    }
  }

  setSpeed(multiplier) {
    this._speed = multiplier;
    if (this._current) this._current.speed = multiplier;
  }

  pause()  { if (this._current) this._current.pause(); }
  resume() { if (this._current) this._current.play(); }

  cancelCurrent() {
    if (this._current) {
      this._current.pause();
      this._current = null;
    }
  }

  destroy() {
    this.cancelCurrent();
    if (this._svg) this._svg.innerHTML = '';
  }
}

if (typeof KnotPlayer !== 'undefined') {
  KnotPlayer.registerAdapter('anime', AnimeAdapter);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = AnimeAdapter;
}
