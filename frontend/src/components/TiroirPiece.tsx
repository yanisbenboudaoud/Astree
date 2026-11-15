/**
 * Tiroir de pièce (annexe D.6) : panneau de 520 px à droite, voile encre à 32 %,
 * `role="dialog"` + `aria-modal`, focus piégé, Échap ferme, le focus revient au déclencheur.
 */
import { useEffect, useRef } from 'react';
import type { Piece } from '../api/types';
import { PastillePiece, Provenance } from './Etiquettes';
import { Icone } from './Icone';
import styles from './TiroirPiece.module.css';

const FOCALISABLES = 'a[href], button:not([disabled]), input, textarea, select, [tabindex]:not([tabindex="-1"])';

export function TiroirPiece({ piece, onFermer }: { piece: Piece; onFermer: () => void }) {
  const panneau = useRef<HTMLDivElement>(null);
  const fermer = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    fermer.current?.focus();
    const surTouche = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onFermer();
        return;
      }
      if (e.key !== 'Tab' || !panneau.current) return;
      const elements = [...panneau.current.querySelectorAll<HTMLElement>(FOCALISABLES)];
      if (!elements.length) return;
      const premier = elements[0];
      const dernier = elements[elements.length - 1];
      if (e.shiftKey && document.activeElement === premier) {
        e.preventDefault();
        dernier.focus();
      } else if (!e.shiftKey && document.activeElement === dernier) {
        e.preventDefault();
        premier.focus();
      }
    };
    document.addEventListener('keydown', surTouche);
    const debordement = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', surTouche);
      document.body.style.overflow = debordement;
    };
  }, [onFermer]);

  const sections = [
    { titre: 'Source', texte: piece.source },
    { titre: 'Traitement', texte: piece.traitement },
    { titre: 'Limites', texte: piece.limites },
  ].filter((s) => s.texte);

  return (
    <div className={styles.voile} onMouseDown={(e) => e.target === e.currentTarget && onFermer()}>
      <div ref={panneau} className={styles.panneau} role="dialog" aria-modal="true" aria-labelledby="titre-piece">
        <div className={styles.entete}>
          <span className={styles.etiquettes}>
            <PastillePiece code={piece.code} />
            <Provenance type={piece.provenance} />
          </span>
          <button ref={fermer} type="button" className={styles.fermer} onClick={onFermer} aria-label={`Fermer la pièce ${piece.code}`}>
            <Icone nom="croix" taille={16} />
          </button>
        </div>
        <div className={styles.titre}>
          <p className="t-etiquette c-500">Pièce à conviction{piece.origine === 'question' ? ' · créée par une question' : ''}</p>
          <h2 id="titre-piece" className="t-h2">{piece.titre}</h2>
          <p className="t-chiffre-moyen">{piece.valeur}</p>
        </div>
        {sections.map((s) => (
          <section key={s.titre} className={styles.section}>
            <h3 className="t-petit-fort c-500">{s.titre}</h3>
            <p className="t-corps">{s.texte}</p>
          </section>
        ))}
        <section className={`${styles.section} ${styles.citee}`}>
          <h3 className="t-petit-fort c-500">Citée par</h3>
          {piece.citeePar?.length ? (
            <ul className={styles.citations}>
              {piece.citeePar.map((c) => (
                <li key={c} className={`t-petit-fort ${c.startsWith('Procureur') ? styles.procureur : c.startsWith('Avocat') ? styles.avocat : ''}`}>{c}</li>
              ))}
            </ul>
          ) : (
            <p className="t-petit c-700">Aucun argument ne cite cette pièce : elle reste au dossier pour le Greffier.</p>
          )}
        </section>
      </div>
    </div>
  );
}
