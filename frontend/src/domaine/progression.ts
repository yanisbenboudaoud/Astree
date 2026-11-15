/**
 * Progression d'un procès (#90) : les 4 phases fixes du Tribunal et les étapes de chacune.
 * Sert au Tribunal en direct (progression réelle publiée par la Lambda, relue toutes les 1,5 s)
 * et à la relecture d'un procès enregistré (sa trace, rejouée étape par étape).
 * Rien n'est animé selon le temps écoulé : une phase n'avance que sur une étape réelle.
 */
import type { EtapeTraceContrat } from '../api/contrat';
import type { EtapeTrace } from '../api/types';

export type PhaseProces = 'agent_profil' | 'orchestrateur' | 'debat' | 'greffier';
export type EtatPhase = 'faite' | 'en_cours' | 'a_venir';

/** Ordre fixe imposé par Python (pipeline/progression.py, PHASES). */
export const PHASES: { id: PhaseProces; libelle: string; detail: string }[] = [
  { id: 'agent_profil', libelle: 'Agent Profil', detail: 'lecture de la demande et du Pacte' },
  { id: 'orchestrateur', libelle: 'Orchestrateur', detail: 'choix des outils, chaque résultat devient une pièce' },
  { id: 'debat', libelle: 'Procureur et Avocat', detail: 'plaidoiries en parallèle, à partir des pièces' },
  { id: 'greffier', libelle: 'Greffier', detail: 'contrôle du Pacte, des chiffres et du cadre' },
];

export function estPhase(valeur: unknown): valeur is PhaseProces {
  return PHASES.some((p) => p.id === valeur);
}

/** Phase d'une étape de trace. Une correction demandée par le Greffier appartient à sa phase. */
export function phaseDeLEtape(etape: Pick<EtapeTraceContrat, 'etape' | 'outil'>): PhaseProces {
  if (etape.etape === 'orchestrateur') return 'orchestrateur';
  if (etape.etape === 'greffier' || etape.outil === 'bedrock_correction') return 'greffier';
  if (etape.etape === 'procureur' || etape.etape === 'avocat') return 'debat';
  return 'agent_profil'; // agent_profil, calibrage (Pacte vécu)
}

/** État de chaque phase : celles d'avant la phase en cours sont faites, les suivantes à venir. */
export function etatsDesPhases(courante: PhaseProces | null, termine: boolean): Record<PhaseProces, EtatPhase> {
  const rang = courante ? PHASES.findIndex((p) => p.id === courante) : -1;
  return Object.fromEntries(PHASES.map((p, i) => {
    if (termine) return [p.id, 'faite'];
    if (i < rang) return [p.id, 'faite'];
    return [p.id, i === rang ? 'en_cours' : 'a_venir'];
  })) as Record<PhaseProces, EtatPhase>;
}

/**
 * Relecture d'un procès enregistré : après `visibles` étapes affichées, la phase en cours est
 * celle de l'étape suivante (elle a commencé) ; null quand toute la trace est affichée.
 */
export function phaseEnRelecture(trace: EtapeTrace[], visibles: number): PhaseProces | null {
  return visibles < trace.length ? trace[visibles].phase : null;
}

/** « 1 argument renvoyé au Procureur » : corrections demandées par le Greffier, par agent. */
export function renvoisDuGreffier(etapes: EtapeTrace[]): string[] {
  return (['Procureur', 'Avocat'] as const).flatMap((role) => {
    const n = etapes.filter((e) => e.phase === 'greffier' && e.role === role).length;
    if (!n) return [];
    const destinataire = role === 'Procureur' ? 'au Procureur' : "à l'Avocat";
    return [`${n} argument${n > 1 ? 's' : ''} renvoyé${n > 1 ? 's' : ''} ${destinataire}`];
  });
}
