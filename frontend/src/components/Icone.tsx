/**
 * Icônes au trait, reprises de la maquette (grille de 24, traits arrondis).
 * Elles prennent la couleur du texte (currentColor) et sont décoratives par défaut :
 * le sens est toujours porté aussi par un mot.
 */
const TRACES: Record<string, string[]> = {
  fiole: ['M10 2v7.5a2 2 0 0 1-.21.9L4.72 20.55a1 1 0 0 0 .9 1.45h12.76a1 1 0 0 0 .9-1.45l-5.07-10.15A2 2 0 0 1 14 9.5V2', 'M8.5 2h7', 'M7 16h10'],
  aide: ['M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z', 'M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3', 'M12 17h.01'],
  'chevron-bas': ['m6 9 6 6 6-6'],
  'chevron-haut': ['m18 15-6-6-6 6'],
  check: ['M5 12.5 9.5 17 19 7.5'],
  'fleche-droite': ['M5 12h14', 'm13 6 6 6-6 6'],
  'fleche-gauche': ['M19 12H5', 'm11 18-6-6 6-6'],
  recherche: ['M17.5 10.75a6.75 6.75 0 1 1-13.5 0 6.75 6.75 0 0 1 13.5 0Z', 'm20 20-4.5-4.5'],
  croix: ['M18 6 6 18', 'm6 6 12 12'],
  interdit: ['M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z', 'm5.6 5.6 12.8 12.8'],
  alerte: ['M10.3 4.2 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0Z', 'M12 9.5v4', 'M12 17h.01'],
  document: ['M14 3H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7Z', 'M14 3v4h4', 'M9.5 13h5', 'M9.5 16.5h5'],
  plus: ['M5 12h14', 'M12 5v14'],
  moins: ['M5 12h14'],
  annuler: ['M9 14 4 9l5-5', 'M4 9h10.5a5.5 5.5 0 0 1 0 11H11'],
};

export type NomIcone = keyof typeof TRACES;

interface ProprietesIcone {
  nom: NomIcone;
  taille?: number;
  /** Épaisseur du trait à l'écran, en pixels (1,5 par défaut, comme la maquette). */
  epaisseur?: number;
  className?: string;
  /** Texte de remplacement : sans lui, l'icône est masquée aux lecteurs d'écran. */
  titre?: string;
}

export function Icone({ nom, taille = 16, epaisseur, className, titre }: ProprietesIcone) {
  const trait = epaisseur ?? (taille <= 14 ? 1.35 : 1.5);
  return (
    <svg
      width={taille}
      height={taille}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={(trait * 24) / taille}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden={titre ? undefined : true}
      role={titre ? 'img' : undefined}
      aria-label={titre}
      focusable="false"
    >
      {TRACES[nom].map((d) => <path key={d} d={d} />)}
    </svg>
  );
}
