/**
 * GlobeCanvas.tsx — ReloPass Animated Globe (Canvas 2D)
 * ─────────────────────────────────────────────────────────────────────────────
 * Flat equirectangular projection. 7 animated Bezier corridor arcs between
 * major relocation cities. requestAnimationFrame loop, ~60fps.
 *
 * Colors: teal #1DBFA2, blue #4A9AE8, amber #EFA827
 * City dot: rgba(255,255,255,0.86)
 * Background: #0A0E1A (matches [color-surface-brand-panel])
 *
 * Decorative only — aria-hidden="true"
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useEffect, useRef } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface CityDef {
  name: string;
  lat: number;
  lng: number;
}

interface ArcDef {
  from: string;
  to: string;
  color: string;
  speed: number; // progress advance per frame (0–1)
  width: number;
}

// ─── Data ─────────────────────────────────────────────────────────────────────

const CITIES: CityDef[] = [
  { name: 'new_york',   lat: 40.71,  lng: -74.01 },
  { name: 'toronto',    lat: 43.65,  lng: -79.38 },
  { name: 'london',     lat: 51.51,  lng: -0.13  },
  { name: 'paris',      lat: 48.86,  lng:  2.35  },
  { name: 'berlin',     lat: 52.52,  lng: 13.40  },
  { name: 'dubai',      lat: 25.20,  lng: 55.27  },
  { name: 'singapore',  lat:  1.35,  lng: 103.82 },
  { name: 'tokyo',      lat: 35.68,  lng: 139.65 },
  { name: 'sydney',     lat: -33.87, lng: 151.21 },
];

const TEAL  = '#1DBFA2';
const BLUE  = '#4A9AE8';
const AMBER = '#EFA827';

const ARCS: ArcDef[] = [
  { from: 'new_york',  to: 'london',    color: TEAL,  speed: 0.0042, width: 1.8 },
  { from: 'toronto',   to: 'london',    color: BLUE,  speed: 0.0038, width: 1.5 },
  { from: 'london',    to: 'berlin',    color: AMBER, speed: 0.0055, width: 1.5 },
  { from: 'paris',     to: 'dubai',     color: TEAL,  speed: 0.0035, width: 1.8 },
  { from: 'london',    to: 'singapore', color: BLUE,  speed: 0.0028, width: 1.5 },
  { from: 'dubai',     to: 'singapore', color: AMBER, speed: 0.0032, width: 1.8 },
  { from: 'singapore', to: 'tokyo',     color: TEAL,  speed: 0.0048, width: 1.5 },
];

// ─── Projection ───────────────────────────────────────────────────────────────

/** Equirectangular: maps (lat, lng) → canvas (x, y) */
function project(lat: number, lng: number, w: number, h: number): [number, number] {
  // Pad edges slightly so arc endpoints aren't clipped
  const pad = 0.06;
  const x = (lng + 180) / 360 * w * (1 - 2 * pad) + w * pad;
  const y = (90 - lat) / 180 * h * (1 - 2 * pad) + h * pad;
  return [x, y];
}

/** Bezier control point — lifted above the chord for arc effect */
function controlPoint(
  x1: number, y1: number,
  x2: number, y2: number,
  lift = 0.35
): [number, number] {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const dx = x2 - x1;
  const dy = y2 - y1;
  // Perpendicular direction, lifted upward (negative y)
  const len = Math.sqrt(dx * dx + dy * dy);
  const nx = -dy / len;
  const ny =  dx / len;
  const liftDist = len * lift;
  return [mx + nx * liftDist, my + ny * liftDist];
}

/** Sample a quadratic Bezier at t ∈ [0,1] */
function bezier(
  x1: number, y1: number,
  cx: number, cy: number,
  x2: number, y2: number,
  t: number
): [number, number] {
  const mt = 1 - t;
  return [
    mt * mt * x1 + 2 * mt * t * cx + t * t * x2,
    mt * mt * y1 + 2 * mt * t * cy + t * t * y2,
  ];
}

// ─── Draw helpers ─────────────────────────────────────────────────────────────

function drawGrid(ctx: CanvasRenderingContext2D, w: number, h: number) {
  ctx.save();
  ctx.strokeStyle = 'rgba(255,255,255,0.04)';
  ctx.lineWidth = 0.5;
  // Latitudes every 30°
  for (let lat = -60; lat <= 60; lat += 30) {
    const [, y] = project(lat, 0, w, h);
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  // Longitudes every 30°
  for (let lng = -180; lng <= 180; lng += 30) {
    const [x] = project(0, lng, w, h);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  ctx.restore();
}

function drawCity(ctx: CanvasRenderingContext2D, x: number, y: number) {
  ctx.save();
  ctx.beginPath();
  ctx.arc(x, y, 3.2, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(255,255,255,0.86)';
  ctx.fill();
  // Outer ring
  ctx.beginPath();
  ctx.arc(x, y, 5.5, 0, Math.PI * 2);
  ctx.strokeStyle = 'rgba(255,255,255,0.22)';
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.restore();
}

// ─── Arc state ────────────────────────────────────────────────────────────────

interface ArcState {
  progress: number;     // head of the travelling segment [0,1]
  tailLen: number;      // length of visible tail (fraction of arc)
  direction: 1 | -1;
}

// ─── Component ────────────────────────────────────────────────────────────────

export interface GlobeCanvasProps {
  className?: string;
  style?: React.CSSProperties;
}

export function GlobeCanvas({ className, style }: GlobeCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Build city lookup
    const cityMap = new Map<string, CityDef>(CITIES.map(c => [c.name, c]));

    // Initialise arc states with spread-out starting positions
    const states: ArcState[] = ARCS.map((_, i) => ({
      progress: (i / ARCS.length) % 1,
      tailLen: 0.22 + Math.random() * 0.12,
      direction: 1,
    }));

    let lastTime = 0;

    function resize() {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas!.getBoundingClientRect();
      canvas!.width  = rect.width  * dpr;
      canvas!.height = rect.height * dpr;
      ctx!.scale(dpr, dpr);
    }

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    resize();

    function frame(ts: number) {
      const dt = Math.min(ts - lastTime, 50); // cap at 50ms to handle tab background
      lastTime = ts;

      const rect = canvas!.getBoundingClientRect();
      const w = rect.width;
      const h = rect.height;

      // Clear
      ctx!.clearRect(0, 0, w, h);

      // Background
      ctx!.fillStyle = '#0A0E1A';
      ctx!.fillRect(0, 0, w, h);

      // Grid
      drawGrid(ctx!, w, h);

      // Draw arcs
      ARCS.forEach((arc, i) => {
        const st = states[i];
        const fromCity = cityMap.get(arc.from);
        const toCity   = cityMap.get(arc.to);
        if (!fromCity || !toCity) return;

        const [x1, y1] = project(fromCity.lat, fromCity.lng, w, h);
        const [x2, y2] = project(toCity.lat,   toCity.lng,   w, h);
        const [cx, cy] = controlPoint(x1, y1, x2, y2);

        // Advance progress
        st.progress += arc.speed * (dt / 16.67);
        if (st.progress > 1 + st.tailLen) {
          st.progress = -st.tailLen;
        }

        const tailStart = Math.max(0, st.progress - st.tailLen);
        const head      = Math.min(1, st.progress);

        if (head > tailStart) {
          // Draw segmented arc from tailStart → head
          const STEPS = 40;
          ctx!.save();
          ctx!.lineCap = 'round';

          for (let s = 0; s < STEPS; s++) {
            const ta = tailStart + (head - tailStart) * (s / STEPS);
            const tb = tailStart + (head - tailStart) * ((s + 1) / STEPS);
            const [ax, ay] = bezier(x1, y1, cx, cy, x2, y2, ta);
            const [bx, by] = bezier(x1, y1, cx, cy, x2, y2, tb);

            // Fade at tail, bright at head
            const segT = s / STEPS;
            const alpha = 0.12 + segT * 0.72;

            ctx!.beginPath();
            ctx!.moveTo(ax, ay);
            ctx!.lineTo(bx, by);
            ctx!.strokeStyle = arc.color + Math.round(alpha * 255).toString(16).padStart(2, '0');
            ctx!.lineWidth = arc.width * (0.5 + segT * 0.5);
            ctx!.stroke();
          }

          // Glowing head dot
          const [hx, hy] = bezier(x1, y1, cx, cy, x2, y2, Math.min(1, st.progress));
          const grd = ctx!.createRadialGradient(hx, hy, 0, hx, hy, 6);
          grd.addColorStop(0, arc.color + 'cc');
          grd.addColorStop(1, arc.color + '00');
          ctx!.beginPath();
          ctx!.arc(hx, hy, 6, 0, Math.PI * 2);
          ctx!.fillStyle = grd;
          ctx!.fill();

          ctx!.restore();
        }
      });

      // Draw cities on top of arcs
      const usedCities = new Set<string>();
      ARCS.forEach(a => { usedCities.add(a.from); usedCities.add(a.to); });
      usedCities.forEach(name => {
        const city = cityMap.get(name);
        if (!city) return;
        const [x, y] = project(city.lat, city.lng, w, h);
        drawCity(ctx!, x, y);
      });

      rafRef.current = requestAnimationFrame(frame);
    }

    rafRef.current = requestAnimationFrame(ts => { lastTime = ts; frame(ts); });

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={className}
      style={{
        display: 'block',
        width: '100%',
        height: '100%',
        ...style,
      }}
    />
  );
}

export default GlobeCanvas;
