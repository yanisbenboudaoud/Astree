/**
 * Courbe de valeur du portefeuille (annexe D.2) : courbe encre de 1,75 px, aire à 6 %,
 * axe en k$ à droite, pastille de la valeur actuelle, point le plus bas annoté, années.
 * Les points viennent de `serieValeur`, calculée par scripts/build_ui_series.py.
 */
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

export function GraphiqueValeur({ serie, pointBas }: ProprietesGraphiqueValeur) {
  const [ref, largeur] = useLargeur<HTMLDivElement>(776);
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

  return (
    <div ref={ref} className={styles.conteneur}>
      <svg width={largeur} height={HAUTEUR} role="img" aria-label={resume} className={styles.svg}>
        {graduations(domaine[0], domaine[1], pas).map((v) => (
          <g key={v}>
            <line x1={0} x2={largeurTrace} y1={y(v)} y2={y(v)} className={styles.repere} />
            <text x={largeurTrace + 14} y={y(v) + 4} className={styles.axe}>{kiloDollars(v)}</text>
          </g>
        ))}
        <path d={aire} className={styles.aire} />
        <path d={ligne} className={styles.courbeValeur} />
        <circle cx={xBas} cy={yBas} r={3.5} className={styles.pointBas} />
        <text x={Math.min(xBas - 4, largeurTrace - 140)} y={yBas - 36} className={styles.annotation}>{etiquetteBas}</text>
        <g transform={`translate(${largeurTrace + 8}, ${y(derniere) - 9})`}>
          <rect width={56} height={20} rx={2} className={styles.pastilleValeur} />
          <text x={28} y={14} textAnchor="middle" className={styles.texteInverse}>{kiloDollars(derniere)}</text>
        </g>
        {debutsAnnees(serie.map(([d]) => d)).map(({ annee, date: d }) => (
          <text key={annee} x={x(jour(d))} y={HAUTEUR - 6} className={styles.axe}>{annee}</text>
        ))}
      </svg>
    </div>
  );
}
