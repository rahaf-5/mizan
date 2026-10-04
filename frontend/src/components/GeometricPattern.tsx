/**
 * Very subtle eight-point star (khatam) lattice, used sparingly as a quiet
 * Islamic accent behind the Home hero. Purely decorative.
 */
export function GeometricPattern({ className = "" }: { className?: string }) {
  return (
    <svg aria-hidden="true" focusable="false" className={className} width="100%" height="100%">
      <defs>
        <pattern id="mizan-khatam" width="56" height="56" patternUnits="userSpaceOnUse">
          <g fill="none" stroke="currentColor" strokeWidth="1">
            <rect x="16" y="16" width="24" height="24" />
            <rect x="16" y="16" width="24" height="24" transform="rotate(45 28 28)" />
          </g>
        </pattern>
        <radialGradient id="mizan-fade" cx="50%" cy="40%" r="60%">
          <stop offset="0%" stopColor="white" stopOpacity="1" />
          <stop offset="100%" stopColor="white" stopOpacity="0" />
        </radialGradient>
        <mask id="mizan-mask">
          <rect width="100%" height="100%" fill="url(#mizan-fade)" />
        </mask>
      </defs>
      <rect width="100%" height="100%" fill="url(#mizan-khatam)" mask="url(#mizan-mask)" />
    </svg>
  );
}
