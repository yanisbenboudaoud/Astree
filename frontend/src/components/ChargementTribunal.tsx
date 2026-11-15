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
          const attenue = etat === 'a_venir' ? 'c-500' : '';
          return (
            <li key={p.id} className={`${styles.phase} ${CLASSES[etat]}`} data-etat={etat} aria-current={etat === 'en_cours' ? 'step' : undefined}>
              <span className={styles.pastille} aria-hidden="true">
                {etat === 'faite' && <Icone nom="check" taille={14} />}
              </span>
              <div className={styles.textePhase}>
                <p>
                  <span className={`t-petit-fort ${attenue}`}>{p.libelle}</span>
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
