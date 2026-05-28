/** Marvis 头像（黑斑马 + 红围巾），原始 SVG 来自 marvis-demo.html。 */
interface Props {
  size?: number;
}

export function MarvisAvatar({ size = 64 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" fill="none">
      <path d="M30 78 Q50 88 70 78 L70 92 Q50 98 30 92 Z" fill="#e5362b" />
      <rect x="44" y="80" width="12" height="16" fill="#e5362b" />
      <path
        d="M50 18 C30 18 24 34 26 52 C27 64 36 76 50 76 C64 76 73 64 74 52 C76 34 70 18 50 18 Z"
        fill="#1a1a1a"
      />
      <path d="M50 8 L46 22 L54 22 Z" fill="#1a1a1a" />
      <path d="M38 12 L37 26 L45 23 Z" fill="#1a1a1a" />
      <path d="M62 12 L63 26 L55 23 Z" fill="#1a1a1a" />
      <path d="M30 24 L26 14 L37 20 Z" fill="#1a1a1a" />
      <path d="M70 24 L74 14 L63 20 Z" fill="#1a1a1a" />
      <ellipse cx="50" cy="62" rx="13" ry="10" fill="#0d0d0d" />
      <circle cx="45" cy="64" r="1.6" fill="#3a3a3a" />
      <circle cx="55" cy="64" r="1.6" fill="#3a3a3a" />
      <ellipse cx="41" cy="46" rx="6" ry="7" fill="#fff" />
      <ellipse cx="59" cy="46" rx="6" ry="7" fill="#fff" />
      <circle cx="42" cy="47" r="3" fill="#1a1a1a" />
      <circle cx="58" cy="47" r="3" fill="#1a1a1a" />
      <circle cx="43" cy="46" r="1" fill="#fff" />
      <circle cx="59" cy="46" r="1" fill="#fff" />
    </svg>
  );
}
