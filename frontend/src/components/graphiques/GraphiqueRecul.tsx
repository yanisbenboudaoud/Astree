/**
 * Recul comparé (annexe D.4) : actuel en encre-300, avec la décision en encre-900,
 * limite du Pacte en pointillé, zone sous la limite en rouge à 22 %, creux annoté,
 * nombre de séances sous la limite. Tout vient des tables précalculées.
 */
import type { SeancesSousLimite } from '../../api/types';
import { moisAnnee, moisLong, pourcent } from '../../lib/format';
import { chemin, debutsAnnees, echelleLineaire, graduations, jour, pasRond, useLargeur } from './echelles';
import styles from './Graphiques.module.css';

interface ProprietesGraphiqueRecul {
  actuel: [string, number][];
  decision: [string, number][];
  limite?: number;
  creux: { date: string; valeur: number };
  seances?: SeancesSousLimite | null;
  libelleDecision: string;
}

const HAUTEUR = 244;
const HAUT = 10;
const HAUTEUR_TRACE = 200;
const GAUCHE = 56;
const DROITE = 20;

export function GraphiqueRecul({ actuel, decision, limite, creux, seances, libelleDecision }: ProprietesGraphiqueRecul) {
  const [ref, largeur] = useLargeur<HTMLDivElement>(776);
  const droite = largeur - DROITE;
  const min = Math.min(...decision.map(([, v]) => v), ...actuel.map(([, v]) => v), limite ?? 0);
  const pas = pasRond(-min, 3);
  const bas = Math.floor((min - 1e-9) / pas) * pas;
  const x = echelleLineaire([jour(decision[0][0]), jour(decision[decision.length - 1][0])], [GAUCHE, droite]);
  const y = echelleLineaire([bas, 0], [HAUT + HAUTEUR_TRACE, HAUT]);
  const points = (serie: [string, number][]) => serie.map(([d, v]) => [x(jour(d)), y(v)] as [number, number]);
  const ligneDecision = chemin(points(decision));
  const ligneActuel = chemin(points(actuel));
  const yLimite = limite !== undefined ? y(limite) : undefined;
  const sousLimite = yLimite !== undefined
    ? `${ligneDecision}L${droite},${yLimite}L${GAUCHE},${yLimite}Z`
    : undefined;
  const xCreux = x(jour(creux.date));
  const yCreux = y(creux.valeur);
  const etiquetteCreux = `${pourcent(creux.valeur)} · ${moisAnnee(creux.date)}`;
  const creuxADroite = xCreux < droite - 170;
  const annotation = seances && seances.nombre > 0 && seances.du && seances.au && limite !== undefined;
  const idClip = `sous-limite-${Math.round(largeur)}`;

  const resume = [
    `Recul depuis le sommet, actuel et ${libelleDecision.toLowerCase()}.`,
    `Pire chute avec la décision : ${etiquetteCreux}.`,
    limite !== undefined ? `Limite du Pacte : ${pourcent(limite, { decimales: 0 })}.` : '',
    annotation ? `${seances!.nombre} séances sous la limite, entre ${moisLong(seances!.du!)} et ${moisLong(seances!.au!)}.` : '',
  ].join(' ');

  return (
    <div ref={ref} className={styles.conteneur}>
      <svg width={largeur} height={HAUTEUR} role="img" aria-label={resume} className={styles.svg}>
        <defs>
          {yLimite !== undefined && (
            <clipPath id={idClip}>
              <rect x={GAUCHE} y={yLimite} width={droite - GAUCHE} height={HAUT + HAUTEUR_TRACE - yLimite + 4} />
            </clipPath>
          )}
        </defs>
        {graduations(bas, 0, pas).map((v) => (
          <g key={v}>
            <line x1={GAUCHE} x2={droite} y1={y(v)} y2={y(v)} className={styles.repere} />
            <text x={GAUCHE - 10} y={y(v) + 4} textAnchor="end" className={styles.axe}>{pourcent(v, { decimales: 0 })}</text>
          </g>
        ))}
        {sousLimite && <path d={sousLimite} clipPath={`url(#${idClip})`} className={styles.zoneSousLimite} />}
        <path d={ligneActuel} className={styles.courbeActuel} />
        <path d={ligneDecision} className={styles.courbeDecision} />
        {yLimite !== undefined && (
          <>
            <line x1={GAUCHE} x2={droite} y1={yLimite} y2={yLimite} className={styles.limite} />
            <text x={droite} y={yLimite + 18} textAnchor="end" className={styles.annotationForte}>
              Limite · {pourcent(limite!, { decimales: 0 })}
            </text>
          </>
        )}
        <circle cx={xCreux} cy={yCreux} r={3.5} className={styles.pointBas} />
        <text
          x={creuxADroite ? xCreux + 12 : xCreux - 12}
          y={Math.min(yCreux + 4, HAUT + HAUTEUR_TRACE - 2)}
          textAnchor={creuxADroite ? 'start' : 'end'}
          className={styles.annotationForte}
        >
          {etiquetteCreux}
        </text>
        {annotation && (
          <text x={GAUCHE + (droite - GAUCHE) * 0.6} y={Math.min(yLimite! + 64, HAUT + HAUTEUR_TRACE - 26)} className={styles.annotation}>
            <tspan className={styles.annotationViolation}>{seances!.nombre} séances sous votre limite</tspan>
            <tspan x={GAUCHE + (droite - GAUCHE) * 0.6} dy={18}>entre {moisLong(seances!.du!)} et {moisLong(seances!.au!)}</tspan>
          </text>
        )}
        {debutsAnnees(decision.map(([d]) => d)).map(({ annee, date: d }) => (
          <text key={annee} x={x(jour(d))} y={HAUTEUR - 8} className={styles.axe}>{annee}</text>
        ))}
      </svg>
      <ul className={styles.legende}>
        <li><span className={styles.traitActuel} aria-hidden="true" />Actuel</li>
        <li><span className={styles.traitDecision} aria-hidden="true" />{libelleDecision}</li>
        {annotation && <li><span className={styles.carreLimite} aria-hidden="true" />Sous la limite du Pacte</li>}
        {limite !== undefined && !annotation && <li><span className={styles.traitLimite} aria-hidden="true" />Limite du Pacte, jamais franchie</li>}
      </ul>
    </div>
  );
}
