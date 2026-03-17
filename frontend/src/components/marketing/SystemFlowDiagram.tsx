import React from 'react';
import {
  FolderPlus,
  CheckCircle,
  FileText,
  Users,
  Activity,
} from 'lucide-react';

export interface ProcessStep {
  title: string;
  description: string;
}

const STEP_ICONS = [
  FolderPlus,
  CheckCircle,
  FileText,
  Users,
  Activity,
] as const;

interface SystemFlowDiagramProps {
  steps: readonly ProcessStep[];
  className?: string;
}

const RADIUS = 200;
const CENTER = 260;
const BUBBLE_WIDTH = 224;
const BUBBLE_HEIGHT = 88;

function positionOnCircle(index: number, total: number) {
  // Five points evenly distributed like a star (0° top, then 72° apart)
  const angle = (-90 + (index * 360) / total) * (Math.PI / 180);
  return {
    x: CENTER + RADIUS * Math.cos(angle),
    y: CENTER + RADIUS * Math.sin(angle),
  };
}

/**
 * Star-shaped workflow — nodes in all directions; boxes sized to show full text.
 */
export const SystemFlowDiagram: React.FC<SystemFlowDiagramProps> = ({
  steps,
  className = '',
}) => {
  const points = steps.map((_, i) => positionOnCircle(i, steps.length));

  return (
    <div
      className={`max-w-2xl mx-auto overflow-x-auto overflow-y-hidden pb-2 ${className}`}
      aria-label="Relocation process steps"
    >
      <div className="relative w-[520px] h-[520px] mx-auto min-w-0 flex-shrink-0">
        <svg
          className="absolute inset-0 w-full h-full overflow-visible"
          aria-hidden
        >
          {/* Star: lines from center to each node — visible medium grey */}
          {points.map((p, i) => (
            <line
              key={i}
              x1={CENTER}
              y1={CENTER}
              x2={p.x}
              y2={p.y}
              stroke="currentColor"
              strokeWidth="1"
              strokeDasharray="3 4"
              className="text-marketing-text-subtle"
            />
          ))}
          {/* Ring connecting the points */}
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RADIUS}
            fill="none"
            stroke="currentColor"
            strokeWidth="1"
            strokeDasharray="4 6"
            className="text-marketing-text-subtle"
          />
          {/* Segments between adjacent nodes */}
          {points.map((p, i) => {
            const next = points[(i + 1) % points.length];
            return (
              <line
                key={`seg-${i}`}
                x1={p.x}
                y1={p.y}
                x2={next.x}
                y2={next.y}
                stroke="currentColor"
                strokeWidth="1"
                strokeDasharray="2 4"
                className="text-marketing-text-subtle"
              />
            );
          })}
        </svg>
        {/* Bubbles: content centered vertically; centers on circle for equidistance */}
        {steps.map((step, i) => {
          const { x, y } = points[i];
          const Icon = STEP_ICONS[i % STEP_ICONS.length];
          const stepNum = i + 1;
          return (
            <div
              key={step.title}
              className="absolute flex flex-col items-center justify-center rounded-xl bg-marketing-surface border border-marketing-border shadow-sm p-3 box-border"
              style={{
                width: BUBBLE_WIDTH,
                height: BUBBLE_HEIGHT,
                left: x - BUBBLE_WIDTH / 2,
                top: y - BUBBLE_HEIGHT / 2,
              }}
            >
              <span
                className="flex items-center justify-center w-6 h-6 rounded-full bg-marketing-primary text-white text-xs font-semibold shadow-sm mb-2 flex-shrink-0"
                aria-label={`Step ${stepNum}`}
              >
                {stepNum}
              </span>
              <div className="flex items-center gap-3 flex-1 min-w-0 w-full">
                <div className="flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-lg bg-marketing-surface-muted text-marketing-primary">
                  <Icon className="w-5 h-5" strokeWidth={1.75} />
                </div>
                <span className="text-sm font-semibold text-marketing-primary leading-snug text-left break-words">
                  {step.title}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
