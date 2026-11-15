/**
 * Les limites des chiffres, là où on les lit (domaine/limites.ts) :
 * - `InfoLimite` : un ⓘ à côté d'un indicateur, qui ouvre ce qu'il mesure et sa limite ;
 * - `LimitesDonnees` : une ligne repliée « Ce que ces chiffres ne disent pas », par écran.
 * Fermés, ils ne prennent qu'une ligne : l'écran reste léger, l'information est à un clic.
 */
import { useEffect, useId, useRef, useState, type CSSProperties } from 'react';
import { createPortal } from 'react-dom';
import { INDICATEURS, LIMITES, LIMITES_PAR_ECRAN, type Ecran, type Indicateur } from '../domaine/limites';
import { Icone } from './Icone';
import styles from './Limites.module.css';

const LARGEUR_BULLE = 300;
const MARGE_ECRAN = 12;

/** Position de la bulle à l'écran : sous le bouton (au-dessus s'il manque de place), toujours dans la fenêtre. */
function placerBulle(bouton: DOMRect): CSSProperties {
  const largeur = Math.min(LARGEUR_BULLE, window.innerWidth - 2 * MARGE_ECRAN);
  const left = Math.min(Math.max(bouton.left - 10, MARGE_ECRAN), window.innerWidth - largeur - MARGE_ECRAN);
  const enDessous = window.innerHeight - bouton.bottom > 200 || bouton.top < 200;
  return enDessous
    ? { left, width: largeur, top: bouton.bottom + 6 }
    : { left, width: largeur, bottom: window.innerHeight - bouton.top + 6 };
}

/**
 * La bulle est rendue au-dessus de la page (portail, position fixe) : aucun tableau ni carte ne
 * peut la couper. Elle se ferme au clic dehors, avec Échap, ou si la page défile.
 */
export function InfoLimite({ indicateur, libelle }: { indicateur: Indicateur; libelle: string }) {
  const [position, setPosition] = useState<CSSProperties | null>(null);
  const id = useId();
  const bouton = useRef<HTMLButtonElement>(null);
  const bulle = useRef<HTMLSpanElement>(null);
  const { mesure, limite } = INDICATEURS[indicateur];
  const ouvert = position !== null;

  useEffect(() => {
    if (!ouvert) return undefined;
    const fermer = () => setPosition(null);
    const fermerDehors = (e: MouseEvent) => {
      const cible = e.target as Node;
      if (!bouton.current?.contains(cible) && !bulle.current?.contains(cible)) fermer();
    };
    const fermerEchap = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        fermer();
        bouton.current?.focus();
      }
    };
    document.addEventListener('mousedown', fermerDehors);
    document.addEventListener('keydown', fermerEchap);
    window.addEventListener('scroll', fermer, true);
    window.addEventListener('resize', fermer);
    return () => {
      document.removeEventListener('mousedown', fermerDehors);
      document.removeEventListener('keydown', fermerEchap);
      window.removeEventListener('scroll', fermer, true);
      window.removeEventListener('resize', fermer);
    };
  }, [ouvert]);

  return (
    <span className={styles.info}>
      <button
        ref={bouton}
        type="button"
        className={styles.boutonInfo}
        aria-expanded={ouvert}
        aria-controls={id}
        aria-label={`${libelle} : ce que mesure ce chiffre et sa limite`}
        onClick={() => setPosition(ouvert ? null : placerBulle(bouton.current!.getBoundingClientRect()))}
      >
        <Icone nom="info" taille={15} />
      </button>
      {ouvert && createPortal(
        <span ref={bulle} id={id} role="note" className={styles.bulle} style={position}>
          <span className={styles.titreBulle}>{libelle}</span>
          <span className={styles.ligneBulle}><strong>Mesure.</strong> {mesure}</span>
          <span className={styles.ligneBulle}><strong>Limite.</strong> {limite}</span>
        </span>,
        document.body,
      )}
    </span>
  );
}

/** Grand écran (paysage) : le panneau des limites est ouvert d'office, il y a la place. */
const GRAND_ECRAN = '(min-width: 1280px)';

function grandEcran(): boolean {
  return typeof window !== 'undefined' && Boolean(window.matchMedia?.(GRAND_ECRAN).matches);
}

/**
 * `ligne` : une ligne repliée sous les chiffres. `panneau` : une carte pour une colonne
 * latérale, ouverte d'office sur grand écran pour qu'on lise les limites sans défiler.
 */
export function LimitesDonnees({ ecran, titre = 'Ce que ces chiffres ne disent pas', variante = 'ligne' }: {
  ecran: Ecran;
  titre?: string;
  variante?: 'ligne' | 'panneau';
}) {
  const panneau = variante === 'panneau';
  const [ouvert, setOuvert] = useState(() => panneau && grandEcran());
  const id = useId();
  const limites = LIMITES_PAR_ECRAN[ecran];
  return (
    <div className={`${styles.limites} ${panneau ? styles.panneau : ''}`}>
      <button type="button" className={styles.boutonLimites} aria-expanded={ouvert} aria-controls={id} onClick={() => setOuvert((o) => !o)}>
        <Icone nom="info" taille={16} />
        <span className={styles.titreLimites}>{titre}</span>
        <span className={styles.nombre}>{limites.length}</span>
        <Icone nom={ouvert ? 'chevron-haut' : 'chevron-bas'} taille={14} />
      </button>
      <ul id={id} hidden={!ouvert} className={styles.liste}>
        {limites.map((cle) => (
          <li key={cle} className={styles.limite}>
            <span className="t-petit-fort">{LIMITES[cle].titre}</span>
            <span className="t-petit c-700">{LIMITES[cle].texte}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
