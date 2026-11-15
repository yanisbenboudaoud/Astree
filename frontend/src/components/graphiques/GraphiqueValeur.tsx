/**
 * Courbe de valeur du portefeuille (annexe D.2) : courbe encre de 1,75 px, aire à 6 %,
 * axe en k$ à droite, pastille de la valeur actuelle, point le plus bas annoté, années.
 * Les points viennent de `serieValeur`, calculée par scripts/build_ui_series.py.
 *
 * Lecture dynamique : au survol, au toucher ou au clavier (← → , Page ↑ ↓, Début, Fin),
 * un repère affiche la date et la valeur du point de la série le plus proche. Ces
 * valeurs sont lues telles quelles dans la série : rien n'est interpolé ni estimé.
 */
import { useState, type KeyboardEvent, type PointerEvent } from 'react';
import { kiloDollars, moisAnnee, pourcent, date as dateFr, dollars } from '../../lib/format';
import { chemin, debutsAnnees, echelleLineaire, graduations, jour, pasRond, useLargeur } from './echelles';
import styles from './Graphiques.module.css';

interface ProprietesGraphiqueValeur {
  serie: [string, number][];
  pointBas: { date: string; valeur: number; recul: number };
}

const HAUTEUR = 236;
const HAUT_TRACE = 8;
const HAUTEUR_TRACE = 200;
const MARGE_DROITE = 76;
const LARGEUR_BULLE = 128;
/** Saut de Page ↑ / Page ↓ : environ un trimestre de points hebdomadaires. */
const SAUT_PAGE = 13;

/** Indice du point dont l'abscisse est la plus proche de `cible` (abscisses croissantes). */
export function indiceLePlusProche(abscisses: number[], cible: number): number {
  let bas = 0;
  let haut = abscisses.length - 1;
  while (haut - bas > 1) {
    const milieu = (bas + haut) >> 1;
    if (abscisses[milieu] <= cible) bas = milieu;
    else haut = milieu;
  }
  return Math.abs(abscisses[haut] - cible) < Math.abs(abscisses[bas] - cible) ? haut : bas;
}

export function GraphiqueValeur({ serie, pointBas }: ProprietesGraphiqueValeur) {
  const [ref, largeur] = useLargeur<HTMLDivElement>(776);
  const [actif, setActif] = useState<number | null>(null);
  const largeurTrace = largeur - MARGE_DROITE;
  const valeurs = serie.map(([, v]) => v);
  const min = Math.min(...valeurs);
  const max = Math.max(...valeurs);
  const pas = pasRond(max - min, 4);
  const plafond = Math.ceil(max / pas) * pas;
  const domaine: [number, number] = [min - pas / 2, plafond - max <= pas / 2 ? plafond : max + pas / 4];
  const x = echelleLineaire([jour(serie[0][0]), jour(serie[serie.length - 1][0])], [0, largeurTrace]);
  const y = echelleLineaire(domaine, [HAUT_TRACE + HAUTEUR_TRACE, HAUT_TRACE]);
  const points = serie.map(([d, v]) => [x(jour(d)), y(v)] as [number, number]);
  const ligne = chemin(points);
  const aire = `${ligne}L${largeurTrace},${HAUT_TRACE + HAUTEUR_TRACE}L0,${HAUT_TRACE + HAUTEUR_TRACE}Z`;
  const [, derniere] = serie[serie.length - 1];
  const xBas = x(jour(pointBas.date));
  const yBas = y(pointBas.valeur);
  const etiquetteBas = `${pourcent(pointBas.recul)} · ${moisAnnee(pointBas.date)}`;
  const resume = `Valeur du portefeuille, de ${dollars(serie[0][1])} le ${dateFr(serie[0][0])} à ${dollars(derniere)} le ${dateFr(serie[serie.length - 1][0])}. Point le plus bas : ${etiquetteBas}.`;

  const suivrePointeur = (evenement: PointerEvent<SVGSVGElement>) => {
    const gauche = evenement.currentTarget.getBoundingClientRect().left;
    setActif(indiceLePlusProche(points.map(([px]) => px), evenement.clientX - gauche));
  };

  const parcourirAuClavier = (evenement: KeyboardEvent<SVGSVGElement>) => {
    const dernier = serie.length - 1;
    const depart = actif ?? dernier;
    const sauts: Record<string, number> = {
      ArrowLeft: depart - 1,
      ArrowRight: depart + 1,
      PageUp: depart - SAUT_PAGE,
      PageDown: depart + SAUT_PAGE,
      Home: 0,
      End: dernier,
    };
    if (evenement.key === 'Escape') {
      setActif(null);
      return;
    }
    if (!(evenement.key in sauts)) return;
    evenement.preventDefault();
    setActif(Math.min(dernier, Math.max(0, sauts[evenement.key])));
  };

  const lecture = actif !== null ? { date: serie[actif][0], valeur: serie[actif][1], x: points[actif][0], y: points[actif][1] } : null;
  const bulleAGauche = lecture !== null && lecture.x + 10 + LARGEUR_BULLE > largeurTrace;

  return (
    <div ref={ref} className={styles.conteneur}>
      <svg
        width={largeur}
        height={HAUTEUR}
        role="img"
        aria-label={resume}
        aria-roledescription="graphique interactif"
        aria-describedby="aide-graphique-valeur"
        tabIndex={0}
        className={`${styles.svg} ${styles.interactif}`}
        onPointerMove={suivrePointeur}
        onPointerDown={suivrePointeur}
        onPointerLeave={() => setActif(null)}
        onKeyDown={parcourirAuClavier}
        onFocus={() => setActif((courant) => courant ?? serie.length - 1)}
        onBlur={() => setActif(null)}
      >
        {graduations(domaine[0], domaine[1], pas).map((v) => (
          <g key={v}>
            <line x1={0} x2={largeurTrace} y1={y(v)} y2={y(v)} className={styles.repere} />
            <text x={largeurTrace + 14} y={y(v) + 4} className={styles.axe}>{kiloDollars(v)}</text>
          </g>
        ))}
        <path d={aire} className={`${styles.aire} ${styles.apparition}`} />
        <path d={ligne} pathLength={1} className={`${styles.courbeValeur} ${styles.dessin}`} />
        <circle cx={xBas} cy={yBas} r={3.5} className={`${styles.pointBas} ${styles.apparition}`} />
        <text x={Math.min(xBas - 4, largeurTrace - 140)} y={yBas - 36} className={`${styles.annotation} ${styles.apparition}`}>{etiquetteBas}</text>
        <g transform={`translate(${largeurTrace + 8}, ${y(derniere) - 9})`}>
          <rect width={56} height={20} rx={2} className={styles.pastilleValeur} />
          <text x={28} y={14} textAnchor="middle" className={styles.texteInverse}>{kiloDollars(derniere)}</text>
        </g>
        {debutsAnnees(serie.map(([d]) => d)).map(({ annee, date: d }) => (
          <text key={annee} x={x(jour(d))} y={HAUTEUR - 6} className={styles.axe}>{annee}</text>
        ))}
        {lecture && (
          <g className={styles.lecture} data-testid="lecture-valeur" pointerEvents="none">
            <line x1={lecture.x} x2={lecture.x} y1={HAUT_TRACE} y2={HAUT_TRACE + HAUTEUR_TRACE} className={styles.repereLecture} />
            <circle cx={lecture.x} cy={lecture.y} r={4.5} className={styles.pointLecture} />
            <g transform={`translate(${bulleAGauche ? lecture.x - 10 - LARGEUR_BULLE : lecture.x + 10}, ${HAUT_TRACE})`}>
              <rect width={LARGEUR_BULLE} height={44} rx={2} className={styles.bulle} />
              <text x={10} y={18} className={styles.bulleDate}>{dateFr(lecture.date)}</text>
              <text x={10} y={36} className={styles.bulleValeur}>{dollars(lecture.valeur)}</text>
            </g>
          </g>
        )}
      </svg>
      <p id="aide-graphique-valeur" className="visuellement-cache">
        Utilisez les flèches gauche et droite pour parcourir la courbe semaine par semaine, Page précédente et Page suivante pour sauter d'un trimestre, Début et Fin pour aller aux extrémités.
      </p>
      <p className="visuellement-cache" aria-live="polite">
        {lecture ? `${dateFr(lecture.date)} : ${dollars(lecture.valeur)}` : ''}
      </p>
    </div>
  );
}
