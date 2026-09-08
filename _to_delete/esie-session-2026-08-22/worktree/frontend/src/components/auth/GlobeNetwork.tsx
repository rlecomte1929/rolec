import React, { useEffect, useRef } from 'react';

// ── GlobeNetwork ────────────────────────────────────────────────────────────
//
// Canvas-2D globe visualization for the public /auth page left panel. Ported
// verbatim from the validated standalone HTML mockup: real-geography
// coastline polygons (checked for self-intersections), Fibonacci-sphere dot
// sampling, marching-squares coastline extraction, great-circle arcs with
// traveling pulses. Do not regenerate the math — this file is a lifecycle
// adaptation (mount once in an effect, clean up the RAF loop + resize
// listener on unmount) of the exact algorithm, not a redesign.

export interface GlobeNetworkConfig {
  rotSpeed: number;
  pulseSpeed: number;
  /** Auto-detected via prefers-reduced-motion when undefined; explicit value overrides either way. */
  reducedMotion?: boolean;
  dotCount: number;
  dotSize: number;
  dotOpacity: number;
  showCoastline: boolean;
  coastColor: string;
  coastWidth: number;
  coastOpacity: number;
  coastGlow: number;
  arcColor: string;
  arcWidth: number;
  arcGlow: number;
  /** 0..1 — fraction of the fixed ARCS route list rendered. */
  arcDensity: number;
  citySize: number;
  showArcs: boolean;
  showCities: boolean;
  showLabels: boolean;
}

// NOTE (flagged for the user): coastOpacity's default of 0.4 is a best-effort
// estimate — the source screenshot this was ported from cropped the exact
// value. Double-check/tune it via the Auth Page Design admin panel
// (frontend/src/pages/admin/AdminAuthPageDesign.tsx) once available.
export const DEFAULT_GLOBE_NETWORK_CONFIG: GlobeNetworkConfig = {
  rotSpeed: 1.9,
  pulseSpeed: 3.4,
  dotCount: 2800,
  dotSize: 1.3,
  dotOpacity: 0.65,
  showCoastline: true,
  coastColor: '#1f8e8b',
  coastWidth: 0.9,
  coastOpacity: 0.4,
  coastGlow: 0,
  arcColor: '#1f8e8b',
  arcWidth: 1.7,
  arcGlow: 20,
  arcDensity: 1.0,
  citySize: 1.0,
  showArcs: true,
  showCities: true,
  showLabels: true,
};

type Vec3 = [number, number, number];
type LatLon = [number, number];

// ── Real-geography coastline model ──────────────────────────────────────────
// Each entry is a hand-traced, simplified polygon (lat/lon vertex ring)
// approximating the actual coastline of a continent, peninsula, or island.
// Verified free of self-intersections. Copied verbatim — do not regenerate.
const POLYGONS: LatLon[][] = [
  [[66,-168],[60,-166],[56,-158],[58,-152],[55,-133],[50,-128],[46,-124],[38,-123],[34,-120],[32,-117],[23,-110],[22,-106],[19,-105],[16,-98],[14,-92],[9,-84],[8,-78],[9,-77.5],[13,-83],[16,-88],[21,-87],[19,-96],[26,-97],[29,-95],[30,-89],[29,-85],[26,-82],[25,-80.3],[27,-80],[30,-81],[32,-80.8],[35,-76],[37,-76],[39,-75.3],[41,-74],[41,-71.9],[43,-70],[45,-67],[47,-64.5],[49,-64],[50,-66],[50,-60],[52,-56],[55,-60],[58,-63],[60,-65],[63,-72],[66,-70],[62,-78],[58,-78],[53,-79],[51,-80.5],[55,-82],[60,-85],[63,-90],[66,-85],[68,-100],[70,-115],[71,-130],[70,-145],[66,-168]],
  [[83,-35],[82,-15],[80,-13],[76,-19],[70,-22],[65,-38],[60,-45],[63,-51],[68,-53],[72,-56],[76,-68],[80,-65],[83,-45],[83,-35]],
  [[12,-72],[11,-70],[11,-64],[8,-59],[5,-52],[-1,-48.5],[-3,-40],[-8,-35],[-13,-38.5],[-17,-39],[-20,-40],[-23,-43],[-26,-48],[-29,-49.5],[-32,-52],[-34,-54],[-35,-57],[-37,-57.5],[-39,-62],[-41,-63],[-43,-65],[-45,-67],[-49,-68],[-52,-69],[-54,-68],[-55,-69],[-54,-71.5],[-52,-73.5],[-48,-75.5],[-44,-74],[-42,-73.7],[-38,-73.3],[-33,-71.7],[-27,-71],[-23,-70.4],[-18,-70.3],[-10,-77.5],[-4,-81],[0,-80.3],[4,-77.3],[7,-77.5],[8,-77.3],[9,-79.5],[12,-72]],
  [[43.8,-9],[43.4,-1.8],[42.4,3.2],[41,3.3],[39,0.2],[37.2,-1.8],[36,-5.4],[37,-7.4],[38.7,-9.4],[41.7,-8.9],[43.8,-9]],
  [[43.5,-1.5],[46,-1.5],[48.5,-4.5],[51,2],[53.5,7],[54.5,10],[54,14],[55,21],[59.5,24.5],[60,30],[65.8,24.1],[69.5,20],[60,40],[50,38],[45.5,36],[41.5,29],[40,23.5],[37.9,22.9],[39.6,20],[42,19.4],[44.8,14.4],[45.7,13.7],[44,7.7],[43.5,-1.5]],
  [[58.5,5.5],[59.5,10.5],[63,10.3],[65.5,12],[68,14.5],[69.5,17.5],[71.1,25.8],[70,28.5],[66,23],[63.5,21],[60.5,17.5],[58.5,11],[55.5,13],[56,12.5],[58.5,5.5]],
  [[58.6,-3],[57.7,-4],[56,-3.5],[54.6,-5.5],[53.4,-3],[51.5,-3.4],[50.1,-5.7],[51,-2],[50.8,1.4],[52.5,1.7],[53.7,0.2],[54.9,-1.2],[55.8,-2],[58.6,-3]],
  [[44,7.7],[45.8,9],[45.6,13.8],[43,14.5],[41.9,15.9],[40.4,17.9],[39.8,17],[38.2,15.6],[37.6,15.3],[38.1,13.4],[39.3,9],[41,8.5],[44,7.7]],
  [[35.7,-5.5],[33,-9.5],[27.7,-13.2],[21,-17],[16.6,-16.5],[12,-16.7],[7,-13.5],[4.5,-7.5],[5.5,-1.5],[6.3,3],[4.3,6.7],[2.3,9.5],[-0.7,8.8],[-4,11.5],[-6,12.2],[-10,13.4],[-15,12],[-17.9,11.8],[-22.9,14.4],[-26,15],[-28.9,16.4],[-34.4,20.4],[-34.8,25],[-33.9,26.9],[-31,29.9],[-27,32.9],[-23.9,35.5],[-20,35.4],[-16,40],[-11,40.5],[-6,39.5],[-3,40.5],[0,42.9],[4,42],[5,44.9],[8,47],[11.8,51.3],[10.4,44.9],[12.5,43.3],[16,39.8],[22,36.9],[27.9,34.6],[31.2,32.3],[32.9,21.5],[32.9,13],[37,10],[35,9],[36.8,3],[35.2,-1.5],[35.7,-5.5]],
  [[-12,49.4],[-15.4,46.3],[-16.7,44.4],[-20.5,44],[-25.6,45.1],[-25.2,46.7],[-22.2,47.9],[-17.3,49.4],[-12,49.4]],
  [[29.5,34.9],[28,34.8],[22,38.8],[16.4,42.5],[12.6,43.5],[17,54.5],[22.5,59.8],[25.6,56.3],[24,51.6],[26,50.8],[32,48],[33,36],[31,35],[31.5,32.3],[29.5,34.9]],
  [[41,29],[41,48],[47,52],[55,62],[60,77],[66,69],[73,84],[76,95],[77.5,106],[73,128],[71,148],[69.5,178.8],[62,179.4],[59.6,162.4],[51.5,156.8],[53,140.7],[48,140],[43,131.6],[39.9,124.4],[37.5,122.4],[35,120],[31.3,121.9],[28,121.6],[23,116.7],[21.5,109],[23,102.2],[28,97],[30,81],[35,77],[37,71],[34,60],[32,50],[37.2,42.4],[37,36],[41,36],[41,29]],
  [[23.6,68.2],[21,72.6],[19,72.8],[15.5,73.5],[12.9,74.9],[9.5,76.3],[8.1,77.5],[10,78.9],[13,80.3],[16.3,81.5],[19.3,85],[21.4,88.1],[22,88.9],[22.3,91.8],[24,92],[26,90.5],[24.7,88],[26.5,84],[28.5,81.1],[29.8,80.2],[28.5,78.9],[29,77],[28.6,76.8],[30.2,74.9],[32.5,74.5],[34.5,74],[34,72],[31.7,71],[29.5,66.4],[25.4,66.4],[23.6,68.2]],
  [[21,97.5],[21.5,105.9],[17,106.6],[10.4,106.8],[1.3,103.8],[5.5,100.2],[9.9,98.4],[16,94.6],[21,97.5]],
  [[45.5,141.9],[43.4,145.8],[41.4,141.4],[38.9,141.5],[35.6,140.8],[34.7,139.7],[33.5,135.8],[33,132],[32.6,130],[34,130.3],[35.5,132.5],[36.6,136.9],[37.9,138.9],[39.8,139.9],[41.2,140],[43,140.9],[45.5,141.9]],
  [[38.6,125.4],[37.7,125.7],[36,126.5],[35.4,126],[34.6,127],[35.1,129.1],[37.5,129.4],[38.6,128.4],[40.7,129.7],[41.4,129.7],[40,124.9],[38.6,125.4]],
  [[5.9,95.3],[-5.8,104.5],[-3,101.8],[0,98.8],[3,96.3],[5.9,95.3]],
  [[-6,105.8],[-8.4,114.5],[-7.7,111],[-6.9,108],[-6,105.8]],
  [[4.2,117.9],[1.5,110.3],[-2,109],[-3.5,114],[-1.5,117.5],[2,118.8],[4.2,117.9]],
  [[1.4,124.8],[-1,120.8],[-3,119.4],[-5.5,120.4],[-4,122.8],[-1,123.4],[1.4,124.8]],
  [[18.5,120.8],[17,122.3],[13.5,123.5],[10,125.6],[6.9,126],[9,123],[11.2,123],[14,120.6],[18.5,120.8]],
  [[-1.4,131.2],[-2.6,141],[-9,147.5],[-10.5,150.9],[-9,142],[-5,136],[-1.4,131.2]],
  [[-10.9,142.5],[-12.5,136.8],[-14.9,135.4],[-11.3,131.9],[-14.9,128.7],[-17.3,122.2],[-20.4,118.9],[-22,113.8],[-26,113.5],[-29,114.9],[-31.9,115.7],[-35,117.9],[-33.9,121.9],[-32,124],[-31.5,131],[-32.2,133.7],[-35,136.9],[-38.4,140.8],[-38.1,144.7],[-37.5,147.9],[-39.1,146.4],[-37.8,150],[-35,150.3],[-30.5,153.1],[-25.3,153.1],[-22.5,150.8],[-19.2,146.8],[-16.8,145.5],[-14.5,144.9],[-10.9,142.5]],
  [[-40.8,144.7],[-41,146.3],[-42.9,147.9],[-43.6,146.4],[-42,144.7],[-40.8,144.7]],
  [[-34.4,172.7],[-36,174.5],[-39.1,177.4],[-39.5,175],[-37,174],[-35,173.2],[-34.4,172.7]],
  [[-40.5,172.7],[-41.3,174.8],[-43.6,172.9],[-45.9,167.5],[-44.4,168.5],[-41.8,171.5],[-40.5,172.7]],
];

function pointInPoly(lat: number, lon: number, poly: LatLon[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [lat1, lon1] = poly[i]!;
    const [lat2, lon2] = poly[j]!;
    if (lon1 > lon !== lon2 > lon) {
      const latCross = lat1 + ((lat2 - lat1) * (lon - lon1)) / (lon2 - lon1);
      if (lat < latCross) inside = !inside;
    }
  }
  return inside;
}

function isLand(lat: number, lon: number): boolean {
  for (const poly of POLYGONS) if (pointInPoly(lat, lon, poly)) return true;
  return false;
}

function landScoreSmooth(lat: number, lon: number): number {
  return isLand(lat, lon) ? 1 : -1;
}

function llToXyz(lat: number, lon: number): Vec3 {
  const latR = (lat * Math.PI) / 180;
  const lonR = (lon * Math.PI) / 180;
  const y = Math.sin(latR);
  const r = Math.cos(latR);
  return [Math.cos(lonR) * r, y, Math.sin(lonR) * r];
}

interface CoastSeg {
  a: Vec3;
  b: Vec3;
}

function buildCoastlineSegments(): CoastSeg[] {
  const LAT_STEP = 2;
  const LON_STEP = 2;
  const lats: number[] = [];
  for (let l = -88; l <= 88; l += LAT_STEP) lats.push(l);
  const lons: number[] = [];
  for (let l = -180; l < 180; l += LON_STEP) lons.push(l);
  const grid = lats.map((la) => lons.map((lo) => landScoreSmooth(la, lo)));
  const interp = (v0: number, v1: number) => v0 / (v0 - v1);
  const segs: CoastSeg[] = [];
  for (let i = 0; i < lats.length - 1; i++) {
    for (let j = 0; j < lons.length - 1; j++) {
      const lat0 = lats[i]!, lat1 = lats[i + 1]!, lon0 = lons[j]!, lon1 = lons[j + 1]!;
      const c0 = grid[i]![j]!, c1 = grid[i]![j + 1]!, c2 = grid[i + 1]![j + 1]!, c3 = grid[i + 1]![j]!;
      const idx = (c0 > 0 ? 1 : 0) | (c1 > 0 ? 2 : 0) | (c2 > 0 ? 4 : 0) | (c3 > 0 ? 8 : 0);
      if (idx === 0 || idx === 15) continue;
      const eBottom: LatLon = [lat0, lon0 + (lon1 - lon0) * interp(c0, c1)];
      const eRight: LatLon = [lat0 + (lat1 - lat0) * interp(c1, c2), lon1];
      const eTop: LatLon = [lat1, lon0 + (lon1 - lon0) * interp(c3, c2)];
      const eLeft: LatLon = [lat0 + (lat1 - lat0) * interp(c0, c3), lon0];
      const TABLE: Record<number, [LatLon, LatLon][]> = {
        1: [[eLeft, eBottom]],
        2: [[eBottom, eRight]],
        3: [[eLeft, eRight]],
        4: [[eRight, eTop]],
        5: [[eLeft, eBottom], [eRight, eTop]],
        6: [[eBottom, eTop]],
        7: [[eLeft, eTop]],
        8: [[eTop, eLeft]],
        9: [[eTop, eBottom]],
        10: [[eBottom, eRight], [eTop, eLeft]],
        11: [[eTop, eRight]],
        12: [[eRight, eLeft]],
        13: [[eRight, eBottom]],
        14: [[eBottom, eLeft]],
      };
      for (const [p0, p1] of TABLE[idx] || []) {
        segs.push({ a: llToXyz(p0[0], p0[1]), b: llToXyz(p1[0], p1[1]) });
      }
    }
  }
  return segs;
}

function slerp(a: Vec3, b: Vec3, t: number): Vec3 {
  const dot = Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]));
  const theta = Math.acos(dot) * t;
  const rx0 = b[0] - a[0] * dot, ry0 = b[1] - a[1] * dot, rz0 = b[2] - a[2] * dot;
  const len = Math.sqrt(rx0 * rx0 + ry0 * ry0 + rz0 * rz0) || 1;
  const rx = rx0 / len, ry = ry0 / len, rz = rz0 / len;
  const ct = Math.cos(theta), st = Math.sin(theta);
  return [a[0] * ct + rx * st, a[1] * ct + ry * st, a[2] * ct + rz * st];
}

function buildLandPoints(count: number): Vec3[] {
  const pts: Vec3[] = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const yv = 1 - (i / (count - 1)) * 2;
    const rY = Math.sqrt(Math.max(0, 1 - yv * yv));
    const theta = golden * i;
    const xv = Math.cos(theta) * rY, zv = Math.sin(theta) * rY;
    const latDeg = (Math.asin(yv) * 180) / Math.PI;
    const lonDeg = (Math.atan2(zv, xv) * 180) / Math.PI;
    if (isLand(latDeg, lonDeg)) pts.push([xv, yv, zv]);
  }
  return pts;
}

interface City {
  name: string;
  lat: number;
  lon: number;
  xyz: Vec3;
}

const CITY_DEFS: Record<string, { name: string; lat: number; lon: number }> = {
  vancouver: { name: 'CA', lat: 49.28, lon: -123.12 },
  newyork: { name: 'US', lat: 40.71, lon: -74.01 },
  london: { name: 'GB', lat: 51.51, lon: -0.13 },
  berlin: { name: 'DE', lat: 52.52, lon: 13.4 },
  oslo: { name: 'NO', lat: 59.91, lon: 10.75 },
  dubai: { name: 'AE', lat: 25.2, lon: 55.27 },
  singapore: { name: 'SG', lat: 1.35, lon: 103.82 },
  saopaulo: { name: 'BR', lat: -23.55, lon: -46.63 },
};

const CITIES: Record<string, City> = Object.fromEntries(
  Object.entries(CITY_DEFS).map(([key, c]) => [key, { ...c, xyz: llToXyz(c.lat, c.lon) }])
);

const ARCS: [string, string][] = [
  ['vancouver', 'berlin'],
  ['newyork', 'london'],
  ['berlin', 'dubai'],
  ['dubai', 'singapore'],
  ['saopaulo', 'newyork'],
];

const TILT = (-20 * Math.PI) / 180;
const DOT_COLOR = '#8fd3cc';

interface Projected {
  sx: number;
  sy: number;
  z2: number;
  depth: number;
  scale: number;
  alpha: number;
  front: boolean;
}

function project(v: Vec3, rotY: number, cx: number, cy: number, R: number): Projected {
  const [x, y, z] = v;
  const x1 = x * Math.cos(rotY) + z * Math.sin(rotY);
  const z1 = -x * Math.sin(rotY) + z * Math.cos(rotY);
  const y1 = y;
  const y2 = y1 * Math.cos(TILT) - z1 * Math.sin(TILT);
  const z2 = y1 * Math.sin(TILT) + z1 * Math.cos(TILT);
  const x2 = x1;
  const depth = -z2;
  return {
    sx: cx + x2 * R,
    sy: cy - y2 * R,
    z2,
    depth,
    scale: 1 + depth * 0.12,
    alpha: Math.max(0, Math.min(1, depth * 1.3 + 0.05)),
    front: z2 <= 0.04,
  };
}

function arcPoint(a: Vec3, b: Vec3, t: number): Vec3 {
  const lift = 1 + Math.sin(t * Math.PI) * 0.32;
  const s = slerp(a, b, t);
  return [s[0] * lift, s[1] * lift, s[2] * lift];
}

// ── Component ────────────────────────────────────────────────────────────────

export interface GlobeNetworkProps {
  config?: Partial<GlobeNetworkConfig>;
}

export const GlobeNetwork: React.FC<GlobeNetworkProps> = ({ config }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const cfgRef = useRef<GlobeNetworkConfig>({ ...DEFAULT_GLOBE_NETWORK_CONFIG, ...config });
  cfgRef.current = { ...DEFAULT_GLOBE_NETWORK_CONFIG, ...config };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext('2d');
    if (!ctx) return undefined;

    const reducedMotionMQ = window.matchMedia('(prefers-reduced-motion: reduce)');
    const coastSegs = buildCoastlineSegments();
    const dotsCache: { count: number; pts: Vec3[] } = { count: -1, pts: [] };

    let rotY = 0.6;
    let lastTs: number | null = null;
    let raf = 0;
    let disposed = false;

    function ensureDots(count: number): Vec3[] {
      const clamped = Math.max(0, Math.floor(count));
      if (dotsCache.count !== clamped) {
        dotsCache.pts = buildLandPoints(Math.max(2, clamped));
        dotsCache.count = clamped;
      }
      return dotsCache.pts;
    }

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas!.getBoundingClientRect();
      const w = Math.max(1, Math.floor(rect.width * dpr));
      const h = Math.max(1, Math.floor(rect.height * dpr));
      if (canvas!.width !== w) canvas!.width = w;
      if (canvas!.height !== h) canvas!.height = h;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener('resize', resize);

    function render(now: number) {
      if (disposed) return;
      const c = cfgRef.current;
      const reducedMotion = c.reducedMotion ?? reducedMotionMQ.matches;
      const dt = lastTs === null ? 0 : (now - lastTs) / 1000;
      lastTs = now;
      if (!reducedMotion) rotY += dt * (c.rotSpeed * 0.07);

      const rect = canvas!.getBoundingClientRect();
      const w = rect.width, h = rect.height;
      const cx = w / 2, cy = h / 2;
      const R = Math.min(w, h) * 0.42;

      ctx!.clearRect(0, 0, w, h);

      // ── Atmosphere glow ──────────────────────────────────────────────────
      const grad = ctx!.createRadialGradient(cx, cy, R * 0.55, cx, cy, R * 1.35);
      grad.addColorStop(0, 'rgba(31,142,139,0.10)');
      grad.addColorStop(1, 'rgba(31,142,139,0)');
      ctx!.fillStyle = grad;
      ctx!.beginPath();
      ctx!.arc(cx, cy, R * 1.35, 0, Math.PI * 2);
      ctx!.fill();

      // ── Rim ───────────────────────────────────────────────────────────────
      ctx!.beginPath();
      ctx!.arc(cx, cy, R, 0, Math.PI * 2);
      ctx!.strokeStyle = 'rgba(148,163,184,0.14)';
      ctx!.lineWidth = 1;
      ctx!.stroke();

      // ── Coastline (drawn under dots; clipped at the horizon) ────────────
      if (c.showCoastline) {
        const drawCoast = (glow: boolean) => {
          ctx!.beginPath();
          for (const seg of coastSegs) {
            const pa = project(seg.a, rotY, cx, cy, R);
            const pb = project(seg.b, rotY, cx, cy, R);
            if (pa.z2 > 0.05 || pb.z2 > 0.05) continue;
            ctx!.moveTo(pa.sx, pa.sy);
            ctx!.lineTo(pb.sx, pb.sy);
          }
          ctx!.strokeStyle = c.coastColor;
          ctx!.lineWidth = c.coastWidth;
          ctx!.globalAlpha = c.coastOpacity;
          if (glow) {
            ctx!.shadowColor = c.coastColor;
            ctx!.shadowBlur = c.coastGlow;
          } else {
            ctx!.shadowBlur = 0;
          }
          ctx!.stroke();
          ctx!.shadowBlur = 0;
          ctx!.globalAlpha = 1;
        };
        if (c.coastGlow > 0) drawCoast(true);
        drawCoast(false);
      }

      // ── Continent dots (Fibonacci-sphere sampled) ───────────────────────
      const pts = ensureDots(c.dotCount);
      ctx!.fillStyle = DOT_COLOR;
      for (const p of pts) {
        const pr = project(p, rotY, cx, cy, R);
        if (!pr.front) continue;
        ctx!.globalAlpha = pr.alpha * c.dotOpacity;
        ctx!.beginPath();
        ctx!.arc(pr.sx, pr.sy, c.dotSize * pr.scale * 0.9, 0, Math.PI * 2);
        ctx!.fill();
      }
      ctx!.globalAlpha = 1;

      // ── Arcs: great-circle slerp with an outward lift + traveling pulse ─
      if (c.showArcs) {
        const arcCount = Math.max(0, Math.min(ARCS.length, Math.round(ARCS.length * c.arcDensity)));
        const segments = 48;
        const cycleT = (now / 1000 / Math.max(0.1, c.pulseSpeed)) % 1;
        for (let ai = 0; ai < arcCount; ai++) {
          const [fromKey, toKey] = ARCS[ai]!;
          const from = CITIES[fromKey];
          const to = CITIES[toKey];
          if (!from || !to) continue;

          ctx!.beginPath();
          for (let s = 0; s <= segments; s++) {
            const t = s / segments;
            const p = arcPoint(from.xyz, to.xyz, t);
            const pr = project(p, rotY, cx, cy, R);
            if (s === 0) ctx!.moveTo(pr.sx, pr.sy);
            else ctx!.lineTo(pr.sx, pr.sy);
          }
          ctx!.strokeStyle = c.arcColor;
          ctx!.lineWidth = c.arcWidth;
          ctx!.shadowColor = c.arcColor;
          ctx!.shadowBlur = c.arcGlow;
          ctx!.globalAlpha = 0.85;
          ctx!.stroke();
          ctx!.shadowBlur = 0;
          ctx!.globalAlpha = 1;

          // Traveling pulse dot
          const pulsePoint = arcPoint(from.xyz, to.xyz, cycleT);
          const pr = project(pulsePoint, rotY, cx, cy, R);
          if (pr.front) {
            ctx!.beginPath();
            ctx!.fillStyle = '#ffffff';
            ctx!.shadowColor = '#ffffff';
            ctx!.shadowBlur = c.arcGlow * 0.6;
            ctx!.globalAlpha = pr.alpha;
            ctx!.arc(pr.sx, pr.sy, c.arcWidth * 1.4, 0, Math.PI * 2);
            ctx!.fill();
            ctx!.shadowBlur = 0;
            ctx!.globalAlpha = 1;
          }
        }
      }

      // ── Cities: pulsing white dot + optional label ──────────────────────
      if (c.showCities) {
        for (const city of Object.values(CITIES)) {
          const pr = project(city.xyz, rotY, cx, cy, R);
          if (!pr.front) continue;
          const pulse = 2 + Math.sin(now / 400 + city.lon) * 0.6;
          ctx!.globalAlpha = pr.alpha;
          ctx!.fillStyle = '#ffffff';
          ctx!.beginPath();
          ctx!.arc(pr.sx, pr.sy, c.citySize * pulse, 0, Math.PI * 2);
          ctx!.fill();
          if (c.showLabels) {
            ctx!.fillStyle = '#cbd5e1';
            ctx!.font = '11px ui-sans-serif, system-ui, sans-serif';
            ctx!.fillText(city.name, pr.sx + 8, pr.sy - 6);
          }
          ctx!.globalAlpha = 1;
        }
      }

      raf = requestAnimationFrame(render);
    }

    raf = requestAnimationFrame(render);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return <canvas ref={canvasRef} aria-hidden="true" className="w-full h-full block" />;
};
