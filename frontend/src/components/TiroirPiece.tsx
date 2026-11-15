/**
 * Tiroir de pièce (annexe D.6) : panneau de 520 px à droite, voile encre à 32 %,
 * `role="dialog"` + `aria-modal`, focus piégé, Échap ferme, le focus revient au déclencheur.
 */
import { useEffect, useRef } from 'react';
import type { Piece } from '../api/types';
import { PastillePiece, Provenance } from './Etiquettes';
import { Icone } from './Icone';
import { DEFINITION_PIECE, decouperEnPoints, guidePiece, numeroPiece } from '../domaine/pieces';
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

  const guide = guidePiece(piece);
  const numero = numeroPiece(piece.code);
  const sources = decouperEnPoints(piece.source);
  const traitement = decouperEnPoints(piece.traitement);
  const limites = decouperEnPoints(piece.limites);

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
          <p className="t-etiquette c-500">
            Pièce {piece.code}{numero ? ` · ${numero === 1 ? '1re' : `${numero}e`} preuve du dossier` : ''}
            {piece.origine === 'question' ? ' · créée par une question' : ''}
          </p>
          <h2 id="titre-piece" className="t-h2">{piece.titre}</h2>
          <p className="t-chiffre-moyen">{piece.valeur}</p>
        </div>
        <details className={styles.definition}>
          <summary className="t-petit-fort">C’est quoi, une pièce (P1, P2, P3…) ?</summary>
          <p className="t-petit c-700">{DEFINITION_PIECE}</p>
        </details>
        {guide && (
          <section className={styles.guide} aria-label="Ce que montre cette pièce">
            <h3 className="t-petit-fort">Ce que montre cette pièce</h3>
            <p className="t-corps">{guide.role}</p>
            {guide.lecture && <p className="t-petit c-700"><strong>Lire le chiffre : </strong>{guide.lecture}</p>}
          </section>
        )}
        {sources.length > 0 && (
          <section className={styles.section}>
            <h3 className="t-petit-fort c-500">D’où viennent les données</h3>
            <ul className={styles.points}>{sources.map((s) => <li key={s} className="t-petit">{s}</li>)}</ul>
          </section>
        )}
        {limites.length > 0 && (
          <section className={styles.section}>
            <h3 className="t-petit-fort c-500">À garder en tête</h3>
            <ul className={styles.points}>{limites.map((s) => <li key={s} className="t-petit">{s}</li>)}</ul>
          </section>
        )}
        {traitement.length > 0 && (
          <details className={`${styles.section} ${styles.details}`}>
            <summary className="t-petit-fort c-500">
              Comment c’est calculé <span className="t-petit c-500">· {traitement.length} {traitement.length > 1 ? 'étapes' : 'étape'}</span>
            </summary>
            <ol className={styles.points}>{traitement.map((s) => <li key={s} className="t-petit">{s}</li>)}</ol>
          </details>
        )}
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
