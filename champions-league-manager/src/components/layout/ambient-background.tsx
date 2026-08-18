/**
 * Trois nappes de couleur qui dérivent et se fondent l'une dans l'autre sur des
 * cycles volontairement premiers entre eux : la teinte dominante change en
 * permanence sans jamais repasser par le même état. Seules l'opacité et les
 * transformations sont animées — la carte graphique s'en charge, le processeur
 * ne repeint rien, ce qui compte quand la page tourne des heures en direct.
 */
export function AmbientBackground() {
  return (
    <div aria-hidden className="ambient" >
      <span className="ambient-layer ambient-a" />
      <span className="ambient-layer ambient-b" />
      <span className="ambient-layer ambient-c" />

      {/* Marquage de terrain en filigrane : l'identité football sans un pixel animé. */}
      <svg
        viewBox="0 0 1200 800"
        preserveAspectRatio="xMidYMid slice"
        className="absolute inset-0 size-full opacity-[0.055]"
      >
        <g fill="none" stroke="white" strokeWidth="2">
          <circle cx="600" cy="400" r="128" />
          <line x1="600" y1="0" x2="600" y2="800" />
          <rect x="0" y="220" width="150" height="360" />
          <rect x="0" y="310" width="62" height="180" />
          <rect x="1050" y="220" width="150" height="360" />
          <rect x="1138" y="310" width="62" height="180" />
          <path d="M0 44 A44 44 0 0 0 44 0" />
          <path d="M1156 0 A44 44 0 0 0 1200 44" />
          <path d="M0 756 A44 44 0 0 1 44 800" />
          <path d="M1200 756 A44 44 0 0 0 1156 800" />
        </g>
        <circle cx="600" cy="400" r="7" fill="white" />
      </svg>
    </div>
  );
}
