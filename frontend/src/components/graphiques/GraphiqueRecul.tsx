/**
 * Recul comparé (annexe D.4, refait en #105) : de combien le portefeuille est sous son dernier sommet,
 * semaine par semaine, aujourd'hui et avec la décision.
 *
 * Lecture en trois temps :
 *  1. une phrase en tête donne la conclusion (limite franchie ou non, pendant combien de séances, quand) ;
 *  2. le graphique montre les deux courbes, la limite du Pacte, la période passée sous la limite
 *     et les deux pires moments annotés ;
 *  3. au survol, au toucher ou au clavier, un repère compare les deux courbes à la même date.
 *
 * Tout vient des tables précalculées : rien n'est interpolé, estimé ni recalculé ici.
 */
import { useState, type KeyboardEvent, type PointerEvent } from 'react';
import type { SeancesSousLimite } from '../../api/types';
import { compte, date as dateFr, moisAnnee, pourcent, seuil } from '../../lib/format';
import { chemin, debutsAnnees, echelleLineaire, graduations, jour, pasRond, useLargeur } from './echelles';
import { indiceLePlusProche } from './GraphiqueValeur';
import styles from './GraphiqueRecul.module.css';

interface ProprietesGraphiqueRecul {
  actuel: [string, number][];
  decision: [string, number][];
  limite?: number;
  /** Pire moment avec la décision. */
  creux: { date: string; valeur: number };
  /** Pire moment du portefeuille actuel. */
  creuxActuel: { date: string; valeur: number };
  seances?: SeancesSousLimite | null;
  libelleDecision: string;
}

const HAUT = 18;
const HAUTEUR_TRACE = 212;
const BAS_AXE = 28;
const HAUTEUR = HAUT + HAUTEUR_TRACE + BAS_AXE;
const GAUCHE = 44;
const DROITE = 12;
const LARGEUR_BULLE = 196;
/** Saut de Page ↑ / Page ↓ : environ un trimestre de points hebdomadaires. */
const SAUT_PAGE = 13;

/** « en déc. 2022 » ou « entre mai 2022 et avr. 2025 ». */
function periode(du: string, au: string): string {
  const debut = moisAnnee(du);
  const fin = moisAnnee(au);
  return debut === fin ? `en ${debut}` : `entre ${debut} et ${fin}`;
}

/** La phrase de lecture et son ton : franchie (rouge), jamais franchie (vert), ou neutre. */
function conclusion(libelle: string, creux: { date: string; valeur: number }, limite?: number, seances?: SeancesSousLimite | null) {
  const pire = `${pourcent(creux.valeur)} en ${moisAnnee(creux.date)}`;
  if (limite === undefined) return { ton: 'neutre', texte: `${libelle}, la pire baisse aurait été de ${pire}.` };
  if (seances && seances.nombre > 0 && seances.du && seances.au) {
    return {
      ton: 'franchie',
      texte: `${libelle}, le portefeuille serait passé sous votre limite de ${seuil(limite)} pendant ${compte(seances.nombre, 'séance')}, ${periode(seances.du, seances.au)}, avec un creux à ${pourcent(creux.valeur)}.`,
    };
  }
  if (seances && seances.nombre === 0) {
    return { ton: 'respectee', texte: `${libelle}, le portefeuille ne serait jamais passé sous votre limite de ${seuil(limite)}. Pire baisse : ${pire}.` };
  }
  // Seuil mesuré par le Pacte vécu (#68) : les séances ont été comptées avec l'ancien seuil, on ne les cite pas.
  return { ton: 'neutre', texte: `${libelle}, la pire baisse aurait été de ${pire}, pour une limite de ${seuil(limite)}.` };
}

export function GraphiqueRecul({ actuel, decision, limite, creux, creuxActuel, seances, libelleDecision }: ProprietesGraphiqueRecul) {
  const [ref, largeur] = useLargeur<HTMLDivElement>(776);
  const [actif, setActif] = useState<number | null>(null);
  const droite = largeur - DROITE;
  const min = Math.min(...decision.map(([, v]) => v), ...actuel.map(([, v]) => v), limite ?? 0);
  const pas = pasRond(-min, 3);
  const bas = Math.floor((min - 1e-9) / pas) * pas;
  const x = echelleLineaire([jour(decision[0][0]), jour(decision[decision.length - 1][0])], [GAUCHE, droite]);
  const y = echelleLineaire([bas, 0], [HAUT + HAUTEUR_TRACE, HAUT]);
  const pointsDecision = decision.map(([d, v]) => [x(jour(d)), y(v)] as [number, number]);
  const pointsActuel = actuel.map(([d, v]) => [x(jour(d)), y(v)] as [number, number]);
  const abscissesActuel = pointsActuel.map(([px]) => px);
  const ligneDecision = chemin(pointsDecision);
  const ligneActuel = chemin(pointsActuel);
  const aireDecision = `${ligneDecision}L${droite},${y(0)}L${GAUCHE},${y(0)}Z`;
  const yLimite = limite !== undefined ? y(limite) : undefined;
  const sousLimite = yLimite !== undefined ? `${ligneDecision}L${droite},${yLimite}L${GAUCHE},${yLimite}Z` : undefined;
  const franchie = Boolean(seances && seances.nombre > 0 && seances.du && seances.au && limite !== undefined);
  const idClip = `sous-limite-${Math.round(largeur)}`;
  const idDegrade = `degrade-recul-${Math.round(largeur)}`;
  const lecture = conclusion(libelleDecision, creux, limite, seances);

  // Pires moments : le point de la décision est annoté sous le creux ; celui d'aujourd'hui aussi
  // s'il est assez loin, sinon il rejoint l'étiquette de la décision sur une deuxième ligne.
  const xCreux = x(jour(creux.date));
  const yCreux = y(creux.valeur);
  const xCreuxActuel = x(jour(creuxActuel.date));
  const yCreuxActuel = y(creuxActuel.valeur);
  const separes = Math.abs(xCreux - xCreuxActuel) > 150;
  const ancre = (px: number) => (px < GAUCHE + 90 ? 'start' : px > droite - 90 ? 'end' : 'middle');
  const yEtiquette = (py: number, lignes: number) => Math.min(py + 22, HAUT + HAUTEUR_TRACE - 6 - (lignes - 1) * 16);

  const point = actif !== null ? {
    date: decision[actif][0],
    avec: decision[actif][1],
    x: pointsDecision[actif][0],
    y: pointsDecision[actif][1],
    ...(() => {
      const i = indiceLePlusProche(abscissesActuel, pointsDecision[actif][0]);
      return { actuel: actuel[i][1], yActuel: pointsActuel[i][1] };
    })(),
  } : null;
  const bulleAGauche = point !== null && point.x + 14 + LARGEUR_BULLE > droite;

  const suivrePointeur = (evenement: PointerEvent<SVGSVGElement>) => {
    const gauche = evenement.currentTarget.getBoundingClientRect().left;
    setActif(indiceLePlusProche(pointsDecision.map(([px]) => px), evenement.clientX - gauche));
  };
  const parcourirAuClavier = (evenement: KeyboardEvent<SVGSVGElement>) => {
    const dernier = decision.length - 1;
    const depart = actif ?? decision.findIndex(([d]) => d === creux.date);
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

  return (
    <div ref={ref} className={styles.graphique}>
      <div className={styles.entete}>
        <p className={`t-petit-fort ${styles.titre}`}>Baisse depuis le dernier sommet</p>
        <ul className={styles.legende} aria-label="Légende">
          <li><span className={styles.traitActuel} aria-hidden="true" />Actuel</li>
          <li><span className={styles.traitDecision} aria-hidden="true" />{libelleDecision}</li>
          {limite !== undefined && <li><span className={styles.traitLimite} aria-hidden="true" />Votre limite</li>}
        </ul>
      </div>
      <p className={`${styles.conclusion} ${styles[lecture.ton]}`}>
        <span className={styles.pastille} aria-hidden="true" />
        <span className="t-petit">{lecture.texte}</span>
      </p>

      <svg
        width={largeur}
        height={HAUTEUR}
        role="img"
        aria-label={`Baisse depuis le dernier sommet, actuel et ${libelleDecision.toLowerCase()}. ${lecture.texte}`}
        aria-roledescription="graphique interactif"
        aria-describedby="aide-graphique-recul"
        tabIndex={0}
        className={styles.svg}
        onPointerMove={suivrePointeur}
        onPointerDown={suivrePointeur}
        onPointerLeave={() => setActif(null)}
        onKeyDown={parcourirAuClavier}
        onBlur={() => setActif(null)}
      >
        <defs>
          <linearGradient id={idDegrade} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" className={styles.degradeHaut} />
            <stop offset="100%" className={styles.degradeBas} />
          </linearGradient>
          {yLimite !== undefined && (
            <clipPath id={idClip}>
              <rect x={GAUCHE} y={yLimite} width={droite - GAUCHE} height={HAUT + HAUTEUR_TRACE - yLimite + 4} />
            </clipPath>
          )}
        </defs>

        {/* Période sous la limite : une bande verticale, pour la voir d'un coup d'œil. */}
        {franchie && (
          <rect
            x={x(jour(seances!.du!)) - 2}
            y={HAUT}
            width={Math.max(4, x(jour(seances!.au!)) - x(jour(seances!.du!)) + 4)}
            height={HAUTEUR_TRACE}
            rx={3}
            className={styles.bandeSousLimite}
          />
        )}

        {graduations(bas, 0, pas).map((v) => (
          <g key={v}>
            <line x1={GAUCHE} x2={droite} y1={y(v)} y2={y(v)} className={v === 0 ? styles.zero : styles.repere} />
            <text x={GAUCHE - 8} y={y(v) + 4} textAnchor="end" className={styles.axe}>{pourcent(v, { decimales: 0 })}</text>
          </g>
        ))}

        <path d={aireDecision} fill={`url(#${idDegrade})`} />
        {sousLimite && <path d={sousLimite} clipPath={`url(#${idClip})`} className={styles.zoneSousLimite} />}
        <path d={ligneActuel} className={styles.courbeActuel} />
        <path d={ligneDecision} className={styles.courbeDecision} />

        {yLimite !== undefined && (
          <g>
            <line x1={GAUCHE} x2={droite} y1={yLimite} y2={yLimite} className={styles.limite} />
            <g transform={`translate(${droite}, ${yLimite - 8})`}>
              <text textAnchor="end" className={styles.etiquetteLimite}>Votre limite · {seuil(limite!)}</text>
            </g>
          </g>
        )}

        {/* Pire moment d'aujourd'hui */}
        <circle cx={xCreuxActuel} cy={yCreuxActuel} r={4} className={styles.pointActuel} />
        {separes && (
          <text x={xCreuxActuel} y={yEtiquette(yCreuxActuel, 1)} textAnchor={ancre(xCreuxActuel)} className={styles.etiquetteActuel}>
            Actuel {pourcent(creuxActuel.valeur)}
          </text>
        )}

        {/* Pire moment avec la décision */}
        <circle cx={xCreux} cy={yCreux} r={5} className={franchie ? styles.pointCreuxFranchi : styles.pointCreux} />
        <text x={xCreux} y={yEtiquette(yCreux, separes ? 1 : 2)} textAnchor={ancre(xCreux)} className={franchie ? styles.etiquetteCreuxFranchi : styles.etiquetteCreux}>
          <tspan>{pourcent(creux.valeur)} · {moisAnnee(creux.date)}</tspan>
          {!separes && (
            <tspan x={xCreux} dy={16} className={styles.etiquetteActuel}>Actuel {pourcent(creuxActuel.valeur)}</tspan>
          )}
        </text>

        {debutsAnnees(decision.map(([d]) => d)).map(({ annee, date: d }) => (
          <text key={annee} x={x(jour(d))} y={HAUTEUR - 8} textAnchor="middle" className={styles.axe}>{annee}</text>
        ))}

        {point && (
          <g data-testid="lecture-recul" pointerEvents="none">
            <line x1={point.x} x2={point.x} y1={HAUT} y2={HAUT + HAUTEUR_TRACE} className={styles.repereLecture} />
            <circle cx={point.x} cy={point.yActuel} r={4} className={styles.pointLectureActuel} />
            <circle cx={point.x} cy={point.y} r={5} className={styles.pointLectureDecision} />
            <g transform={`translate(${bulleAGauche ? point.x - 14 - LARGEUR_BULLE : point.x + 14}, ${HAUT + 4})`}>
              <rect width={LARGEUR_BULLE} height={74} rx={10} className={styles.bulle} />
              <text x={12} y={20} className={styles.bulleDate}>Semaine du {dateFr(point.date)}</text>
              <rect x={12} y={33} width={10} height={3} rx={1.5} className={styles.puceActuel} />
              <text x={28} y={39} className={styles.bulleLibelle}>Actuel</text>
              <text x={LARGEUR_BULLE - 12} y={39} textAnchor="end" className={styles.bulleValeur}>{pourcent(point.actuel)}</text>
              <rect x={12} y={54} width={10} height={3} rx={1.5} className={styles.puceDecision} />
              <text x={28} y={60} className={styles.bulleLibelle}>Avec la décision</text>
              <text x={LARGEUR_BULLE - 12} y={60} textAnchor="end" className={`${styles.bulleValeur} ${limite !== undefined && point.avec < limite ? styles.bulleValeurFranchie : ''}`}>
                {pourcent(point.avec)}
              </text>
            </g>
          </g>
        )}
      </svg>
      <p id="aide-graphique-recul" className="visuellement-cache">
        Utilisez les flèches gauche et droite pour comparer les deux courbes semaine par semaine, Page précédente et Page suivante pour sauter d'un trimestre, Début et Fin pour aller aux extrémités.
      </p>
      <p className="visuellement-cache" aria-live="polite">
        {point ? `Semaine du ${dateFr(point.date)} : actuel ${pourcent(point.actuel)}, avec la décision ${pourcent(point.avec)}` : ''}
      </p>
    </div>
  );
}
