/** Provenance (Fait, Hypothèse, Fictif), Statut du Greffier et pastille de Pièce (annexe A.4). */
import type { Provenance as TypeProvenance, Statut as TypeStatut } from '../api/types';
import { createContext, useContext } from 'react';
import { Icone } from './Icone';
import styles from './Etiquettes.module.css';

const CLASSES_PROVENANCE: Record<TypeProvenance, string> = {
  Fait: styles.fait,
  Hypothèse: styles.hypothese,
  Fictif: styles.fictif,
};

const DESCRIPTIONS: Record<TypeProvenance, string> = {
  Fait: 'donnée calculée ou règle déclarée, avec sa source',
  Hypothèse: 'interprétation ou information à confirmer',
  Fictif: 'profil, portefeuille ou scénario simulé',
};

export function Provenance({ type }: { type: TypeProvenance }) {
  return (
    <span className={`${styles.provenance} ${CLASSES_PROVENANCE[type]}`} title={DESCRIPTIONS[type]}>
      <svg className={styles.glyphe} width="9" height="9" viewBox="0 0 9 9" aria-hidden="true" focusable="false">
        {type === 'Hypothèse' ? (
          <>
            <circle cx="4.5" cy="4.5" r="3.875" fill="none" stroke="currentColor" strokeWidth="1.25" />
            <path d="M4.5 0.625a3.875 3.875 0 0 0 0 7.75Z" fill="currentColor" />
          </>
        ) : (
          <circle cx="4.5" cy="4.5" r="3.875" fill={type === 'Fait' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.25" />
        )}
      </svg>
      {type}
    </span>
  );
}

const STATUTS: Record<TypeStatut, { classe: string; icone: 'interdit' | 'alerte' | 'check' }> = {
  Violation: { classe: styles.violation, icone: 'interdit' },
  'À vérifier': { classe: styles.verifier, icone: 'alerte' },
  Conforme: { classe: styles.conforme, icone: 'check' },
};

export function Statut({ type, attenue = false }: { type: TypeStatut; attenue?: boolean }) {
  const { classe, icone } = STATUTS[type];
  return (
    <span className={`${styles.statut} ${classe} ${attenue ? styles.attenue : ''}`}>
      <Icone nom={icone} taille={14} />
      {type}
    </span>
  );
}

/** Icône de statut seule (journal, chronologie), avec le statut en texte caché. */
export function IconeStatut({ type, taille = 16 }: { type: TypeStatut; taille?: number }) {
  const { icone } = STATUTS[type];
  const couleur = type === 'Violation' ? styles.texteViolation : type === 'À vérifier' ? styles.texteVerifier : styles.texteConforme;
  return (
    <span className={`${styles.iconeSeule} ${couleur}`}>
      <Icone nom={icone} taille={taille} titre={type} />
    </span>
  );
}

/** Titre de chaque pièce, par code (« P2 » → « Simulation du portefeuille… ») : bulle des pastilles. */
export const TitresPieces = createContext<Record<string, string>>({});

interface ProprietesPiece {
  code: string;
  onOuvrir?: (code: string, declencheur: HTMLElement) => void;
}

export function PastillePiece({ code, onOuvrir }: ProprietesPiece) {
  const titre = useContext(TitresPieces)[code];
  const contenu = (
    <>
      <Icone nom="document" taille={12} epaisseur={1.2} />
      {code}
    </>
  );
  if (!onOuvrir) return <span className={styles.piece} title={titre ? `Pièce ${code} : ${titre}` : undefined}>{contenu}</span>;
  return (
    <button
      type="button"
      className={`${styles.piece} ${styles.pieceBouton}`}
      onClick={(e) => onOuvrir(code, e.currentTarget)}
      aria-label={titre ? `Ouvrir la pièce ${code} : ${titre}` : `Ouvrir la pièce ${code}`}
      title={titre ? `Pièce ${code} : ${titre}` : undefined}
      aria-haspopup="dialog"
    >
      {contenu}
    </button>
  );
}
