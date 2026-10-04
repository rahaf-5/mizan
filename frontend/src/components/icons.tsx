/** Decorative inline icons. Always aria-hidden: meaning is carried by adjacent text. */
type IconProps = { className?: string };

const base = (className = "size-5") => ({
  className,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  focusable: false,
});

export const ScalesIcon = ({ className }: IconProps) => (
  <svg {...base(className)}>
    <path d="M12 3v18M7 21h10M5 7h14M12 5l-7 2M12 5l7 2" />
    <path d="M5 7l-3 6a3 3 0 0 0 6 0L5 7zM19 7l-3 6a3 3 0 0 0 6 0l-3-6z" />
  </svg>
);

export const BoltIcon = ({ className }: IconProps) => (
  <svg {...base(className)}>
    <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z" />
  </svg>
);

export const DocumentIcon = ({ className }: IconProps) => (
  <svg {...base(className)}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5z" />
    <path d="M14 3v5h5M9 13h6M9 17h6" />
  </svg>
);

export const AlertIcon = ({ className }: IconProps) => (
  <svg {...base(className)}>
    <path d="M12 9v4M12 17h.01" />
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
  </svg>
);

export const InfoIcon = ({ className }: IconProps) => (
  <svg {...base(className)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5M12 8h.01" />
  </svg>
);

export const CheckCircleIcon = ({ className }: IconProps) => (
  <svg {...base(className)}>
    <circle cx="12" cy="12" r="9" />
    <path d="m8 12 3 3 5-6" />
  </svg>
);

/** Points "forward" in RTL (towards the left). */
export const ForwardArrowIcon = ({ className }: IconProps) => (
  <svg {...base(className)}>
    <path d="M19 12H5M11 6l-6 6 6 6" />
  </svg>
);

/** Points "back" in RTL (towards the right). */
export const BackArrowIcon = ({ className }: IconProps) => (
  <svg {...base(className)}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);
