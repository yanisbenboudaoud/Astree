/**
 * Écran « Le Tribunal instruit le dossier » (annexe D.5, #90) : les 4 phases fixes du procès,
 * la phase en cours animée, et sous chaque phase ses étapes réelles, au fur et à mesure.
 * - En direct : la progression publiée par la Lambda, relue pendant le procès.
 * - En démonstration : la trace d'un procès enregistré, relue étape par étape à un rythme fixe annoncé.
 * Rien n'avance selon le temps écoulé : une phase change seulement sur une étape réelle.
 */
import { useEffect, useState } from 'react';
import type { EtapeTrace } from '../api/types';
import { Icone } from './Icone';
import { PHASES, etatsDesPhases, renvoisDuGreffier, type EtatPhase, type PhaseProces } from '../domaine/progression';
import styles from './ChargementTribunal.module.css';

export interface PropsChargement {
  mode: 'direct' | 'relecture';
  /** Phase en cours ; null avant la première étape. */
  phase: PhaseProces | null;
  /** Étapes déjà observées, dans l'ordre. */
  etapes: EtapeTrace[];
  termine: boolean;
  activite?: string;
  avis?: string;
  /** Début du procès (compteur de secondes, en direct). */
  debut: number;
  /** Relecture : durée d'une étape, annoncée à l'écran. */
  dureeEtapeMs?: number;
}

const CLASSES: Record<EtatPhase, string> = { faite: styles.phaseFaite, en_cours: styles.phaseEnCours, a_venir: styles.phaseAVenir };
const LIBELLES_ETAT: Record<EtatPhase, string> = { faite: 'terminée', en_cours: 'en cours', a_venir: 'à venir' };

function secondes(ms: number): string {
  return String(ms / 1000).replace('.', ',');
}

/** « Orchestrateur » n'est pas répété sous sa phase ; « Procureur », « Pacte vécu »… le sont. */
function texteEtape(etape: EtapeTrace, libellePhase: string): string {
  const role = etape.role === libellePhase ? '' : `${etape.role} · `;
  return `${role}${etape.appel}${etape.sortie ? ` → ${etape.sortie}` : ''}`;
}

export function ChargementTribunal({ mode, phase, etapes, termine, activite, avis, debut, dureeEtapeMs = 500 }: PropsChargement) {
  const [ecoule, setEcoule] = useState(0);
  useEffect(() => {
    if (termine || mode !== 'direct') return undefined;
    const minuterie = setInterval(() => setEcoule(Math.round((Date.now() - debut) / 1000)), 1000);
    return () => clearInterval(minuterie);
  }, [termine, mode, debut]);

  const etats = etatsDesPhases(phase, termine);
  const enCours = PHASES.find((p) => etats[p.id] === 'en_cours');
  const renvois = renvoisDuGreffier(etapes);
  let introduction: string;
  if (termine) introduction = 'Instruction terminée : voici les étapes tracées.';
  else if (mode === 'relecture') {
    introduction = `Relecture d'un procès enregistré, réellement tenu par les agents Bedrock : une étape toutes les ${secondes(dureeEtapeMs)} s.`;
  } else {
    introduction = `Les agents travaillent en direct : chaque étape s'affiche au moment où elle a lieu. Un procès dure souvent 20 à 40 secondes${ecoule ? ` (${ecoule} s)` : ''}.`;
  }
  let annonce = 'Procès accepté : démarrage des agents';
  if (termine) annonce = 'Instruction terminée';
  else if (enCours) annonce = `Phase en cours : ${enCours.libelle}`;

  return (
    <section className={styles.chargement} aria-labelledby="titre-chargement" aria-busy={!termine}>
      <h1 className="t-h1" id="titre-chargement">Le Tribunal instruit le dossier</h1>
      <p className="t-citation c-700">{introduction}</p>
      <p className="visuellement-cache" aria-live="polite">{annonce}</p>
      <ol className={styles.phases}>
        {PHASES.map((p) => {
          const etat = etats[p.id];
          const etapesPhase = etapes.filter((e) => e.phase === p.id);
          // Phase à venir : nom en encre-700 et détail en encre-500, assez contrastés pour être lus (#103).
          const attenue = etat === 'a_venir' ? 'c-500' : '';
          return (
            <li key={p.id} className={`${styles.phase} ${CLASSES[etat]}`} data-etat={etat} aria-current={etat === 'en_cours' ? 'step' : undefined}>
              <span className={styles.pastille} aria-hidden="true">
                {etat === 'faite' && <Icone nom="check" taille={14} />}
              </span>
              <div className={styles.textePhase}>
                <p>
                  <span className={`t-petit-fort ${attenue ? 'c-700' : ''}`}>{p.libelle}</span>
                  <span className={`t-petit ${attenue || 'c-700'}`}> · {p.detail}</span>
                  <span className="visuellement-cache"> ({LIBELLES_ETAT[etat]})</span>
                </p>
                {etat === 'en_cours' && activite && (
                  <p className="t-petit c-700">{activite.replace(/[.…]$/, '')}…</p>
                )}
                {etapesPhase.length > 0 && (
                  <ol className={styles.etapes}>
                    {etapesPhase.map((e, i) => (
                      <li key={i} className={styles.etape}>
                        <span className={`${styles.iconeEtape} ${e.etat === 'signalement' ? styles.iconeSignalement : ''}`} aria-hidden="true">
                          <Icone nom={e.etat === 'signalement' ? 'alerte' : 'check'} taille={14} />
                        </span>
                        <span>
                          <code className="t-trace c-700">{texteEtape(e, p.libelle)}</code>
                          {e.raison && <span className="t-petit c-700"> · {e.raison}</span>}
                          {e.etat === 'signalement' && <span className="visuellement-cache"> (signalement)</span>}
                        </span>
                      </li>
                    ))}
                  </ol>
                )}
                {p.id === 'greffier' && renvois.length > 0 && <p className="t-petit-fort">{renvois.join(' · ')}</p>}
              </div>
            </li>
          );
        })}
      </ol>
      {avis && !termine && <p className={`t-petit ${styles.avis}`} role="status">{avis}</p>}
    </section>
  );
}

/** Une pièce versée : une étape dont la sortie est « P1 », « P2 »… */
const PIECE = /^P\d+$/;

/**
 * Colonne de droite de l'attente (#103) : le dossier que le Tribunal instruit. La décision et les
 * règles du Pacte sont connues avant le procès ; les pièces s'ajoutent au fil des étapes réelles.
 */
export function DossierInstruit({ decision, regles, etapes }: { decision: string; regles: { id: string; libelle: string }[]; etapes: EtapeTrace[] }) {
  const pieces = etapes.filter((e) => e.sortie && PIECE.test(e.sortie));
  return (
    <section className={styles.dossier} aria-labelledby="titre-dossier">
      <h2 className="t-panneau" id="titre-dossier">Le dossier</h2>
      <div className={styles.rubrique}>
        <p className="t-petit-fort c-500">Décision jugée</p>
        <p className="t-intertitre">{decision}</p>
      </div>
      <div className={styles.rubrique}>
        <p className="t-petit-fort c-500">Règles de votre Pacte</p>
        <ol className={styles.reglesDossier}>
          {regles.map((r, i) => (
            <li key={r.id}>
              <span className="t-trace c-500">§{i + 1}</span>
              <span className="t-petit">{r.libelle}</span>
            </li>
          ))}
        </ol>
      </div>
      <div className={styles.rubrique}>
        <p className="t-petit-fort c-500">Pièces versées au dossier · {pieces.length}</p>
        {pieces.length ? (
          <ul className={styles.piecesDossier}>
            {pieces.map((e) => (
              <li key={e.sortie} className={styles.pieceDossier}>
                <span className={styles.codePiece}>{e.sortie}</span>
                <code className="t-trace c-700">{e.appel.split('(')[0]}</code>
              </li>
            ))}
          </ul>
        ) : (
          <p className="t-petit c-700">Aucune pièce pour l'instant : chaque outil appelé en versera une.</p>
        )}
      </div>
    </section>
  );
}
